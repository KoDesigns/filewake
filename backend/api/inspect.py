from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from backend.api.common import parse_upload
from backend.config import get_settings
from backend.conversion.dispatcher import Dispatcher
from backend.conversion.registry import registry
from backend.runtime.semaphore import conversion_semaphore
from backend.runtime.workspace import Workspace
from backend.security.file_validation import validate_input
from backend.security.limits import copy_upload_limited
from backend.security.mime_detection import font_desktop_format


router = APIRouter()


@router.post("/inspect")
async def inspect_file(request: Request) -> dict:
    settings = get_settings()
    parsed = await parse_upload(request, settings, require_output=False)
    try:
        with Workspace(settings) as workspace:
            initial_path = workspace.path / "input.bin"
            size = await copy_upload_limited(parsed.upload, initial_path, settings.max_file_size_bytes)
            detection = validate_input(initial_path, parsed.upload.filename, parsed.upload.content_type)
            input_path = workspace.input_path(detection.format)
            initial_path.replace(input_path)
            category = registry.category_for(detection.format)
            possible_outputs = registry.possible_outputs(detection.format)
            if detection.format in {"woff", "woff2"}:
                desktop = font_desktop_format(input_path)
                possible_outputs = [desktop] if desktop else []
            details: dict = {}
            if category in {"image", "video"}:
                async with conversion_semaphore:
                    details = await asyncio.to_thread(Dispatcher(settings).inspect, input_path, category)
                if category == "video":
                    details = {
                        "duration": details.get("format", {}).get("duration"),
                        "streams": [
                            {"type": item.get("codec_type"), "codec": item.get("codec_name")}
                            for item in details.get("streams", [])
                            if item.get("codec_type") in {"audio", "video"}
                        ],
                    }
            return {
                "filename": parsed.upload.filename or "file",
                "extension_format": detection.extension_format,
                "detected_format": detection.format,
                "mime": detection.mime,
                "provided_mime": detection.provided_mime,
                "category": category,
                "size": size,
                "mismatch": detection.mismatch,
                "mime_mismatch": detection.mime_mismatch,
                "confidence": detection.confidence,
                "possible_outputs": possible_outputs,
                "default_output": registry.default_output(detection.format),
                "details": details,
            }
    finally:
        await parsed.close()
