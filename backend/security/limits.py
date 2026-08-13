from __future__ import annotations

from pathlib import Path

from backend.errors import ConverterError


async def copy_upload_limited(upload, destination: Path, max_bytes: int) -> int:
    size = 0
    try:
        with destination.open("xb") as target:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise ConverterError(
                        "file_too_large",
                        "The uploaded file exceeds the configured size limit.",
                        413,
                    )
                target.write(chunk)
    except OSError as exc:
        if getattr(exc, "errno", None) == 28:
            raise ConverterError(
                "temporary_storage_full",
                "Temporary storage is full.",
                507,
            ) from exc
        raise
    if size == 0:
        raise ConverterError("invalid_file", "The uploaded file is empty.", 422)
    return size
