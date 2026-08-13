from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, Request
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from backend.api.common import parse_upload
from backend.config import get_settings
from backend.conversion.dispatcher import Dispatcher
from backend.conversion.registry import registry
from backend.errors import ConverterError
from backend.runtime.semaphore import conversion_semaphore
from backend.runtime.workspace import Workspace
from backend.security.file_validation import validate_input, validate_output
from backend.security.filenames import content_disposition, safe_download_name
from backend.security.limits import copy_upload_limited
from backend.security.mime_detection import font_desktop_format


router = APIRouter()
logger = logging.getLogger("converter")


@router.post("/convert", response_class=FileResponse)
async def convert_file(request: Request) -> FileResponse:
    settings = get_settings()
    parsed = await parse_upload(request, settings, require_output=True)
    workspace = Workspace(settings)
    started = time.monotonic()
    input_format = "unknown"
    engine = "unknown"
    try:
        initial_path = workspace.path / "input.bin"
        input_size = await copy_upload_limited(parsed.upload, initial_path, settings.max_file_size_bytes)
        detection = validate_input(initial_path, parsed.upload.filename, parsed.upload.content_type)
        input_format = detection.format
        output_format = parsed.output_format or ""
        spec = registry.require(input_format, output_format)
        if input_format in {"woff", "woff2"} and output_format != font_desktop_format(initial_path):
            raise ConverterError(
                "unsupported_conversion",
                "A webfont can only be restored to its original desktop outline format.",
                422,
            )
        input_path = workspace.input_path(input_format)
        initial_path.replace(input_path)
        output_path = workspace.output_path(output_format)
        async with conversion_semaphore:
            result = await asyncio.to_thread(
                Dispatcher(settings).convert,
                input_path,
                output_path,
                input_format,
                output_format,
                workspace.path,
            )
        engine = result.engine
        output_size = validate_output(result.path, output_format, settings.max_output_size_bytes)
        download_name = safe_download_name(parsed.upload.filename, output_format)
        duration = time.monotonic() - started
        logger.info(
            "conversion category=%s %s->%s engine=%s size=%d duration=%.3f success=true",
            spec.category,
            input_format,
            output_format,
            engine,
            input_size,
            duration,
        )
        return FileResponse(
            path=result.path,
            media_type=spec.output_mime,
            filename=download_name,
            headers={
                "Content-Disposition": content_disposition(download_name),
                "X-Input-Format": input_format,
                "X-Output-Format": output_format,
                "X-Conversion-Engine": engine,
                "X-Original-Size": str(input_size),
                "X-Converted-Size": str(output_size),
                "Cache-Control": "no-store",
            },
            background=BackgroundTask(workspace.cleanup),
        )
    except Exception:
        workspace.cleanup()
        logger.info(
            "conversion category=unknown %s->%s engine=%s duration=%.3f success=false",
            input_format,
            parsed.output_format or "unknown",
            engine,
            time.monotonic() - started,
        )
        raise
    finally:
        await parsed.close()
