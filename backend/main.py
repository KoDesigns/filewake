from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from backend.api import convert, formats, health, info, inspect
from backend.config import get_settings
from backend.errors import ConverterError
from backend.runtime.workspace import cleanup_stale_workspaces


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    cleanup_stale_workspaces(get_settings())
    yield


class RequestSizeLimitMiddleware:
    """Bound request bytes even when a client omits or lies about Content-Length."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] not in {"/api/inspect", "/api/convert"}:
            await self.app(scope, receive, send)
            return
        limit = get_settings().max_request_size_bytes
        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > limit:
                    response = JSONResponse(
                        {"error": "file_too_large", "message": "The request exceeds the configured size limit."},
                        status_code=413,
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                response = JSONResponse(
                    {"error": "invalid_file", "message": "Content-Length is invalid."},
                    status_code=400,
                )
                await response(scope, receive, send)
                return
        consumed = 0

        async def limited_receive():
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > limit:
                    raise ConverterError("file_too_large", "The request exceeds the configured size limit.", 413)
            return message

        await self.app(scope, limited_receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        async def secure_send(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.extend(
                    [
                        (b"content-security-policy", b"default-src 'self'; connect-src 'self'; img-src 'self' blob: data:; font-src 'self' blob:; media-src 'self' blob:; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
                    ]
                )
            await send(message)

        await self.app(scope, receive, secure_send)


app = FastAPI(
    title="Filewake Conversion API",
    version=get_settings().app_version,
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(ConverterError)
async def converter_error_handler(_request: Request, exc: ConverterError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message},
        headers={"Cache-Control": "no-store"},
    )


for api_router in (health.router, info.router, formats.router, inspect.router, convert.router):
    app.include_router(api_router, prefix="/api")


static_dir = Path(__file__).parent / "static"
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
