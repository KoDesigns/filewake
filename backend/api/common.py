from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from starlette.datastructures import FormData, UploadFile

from backend.config import Settings
from backend.errors import ConverterError


@dataclass(slots=True)
class ParsedUpload:
    form: FormData
    upload: UploadFile
    output_format: str | None

    async def close(self) -> None:
        await self.form.close()


async def parse_upload(request: Request, settings: Settings, require_output: bool) -> ParsedUpload:
    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith("multipart/form-data"):
        raise ConverterError("invalid_file", "Expected multipart form data.", 415)
    try:
        form = await request.form(
            max_files=1,
            max_fields=1 if require_output else 0,
            max_part_size=settings.max_request_size_bytes,
        )
    except ConverterError:
        raise
    except Exception as exc:
        raise ConverterError("invalid_file", "The multipart request is invalid or exceeds its limits.", 400) from exc

    allowed = {"file", "output_format"} if require_output else {"file"}
    if set(form.keys()) != allowed:
        await form.close()
        raise ConverterError("invalid_file", "The multipart request contains unexpected or missing fields.", 400)
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        await form.close()
        raise ConverterError("invalid_file", "A file upload is required.", 400)
    output = form.get("output_format") if require_output else None
    if require_output and (not isinstance(output, str) or not output.strip()):
        await form.close()
        raise ConverterError("unsupported_conversion", "An output format is required.", 400)
    normalized_output = output.lower().strip().lstrip(".") if isinstance(output, str) else None
    if normalized_output and (len(normalized_output) > 12 or not normalized_output.isalnum()):
        await form.close()
        raise ConverterError("unsupported_conversion", "The output format is invalid.", 400)
    return ParsedUpload(form, upload, normalized_output)
