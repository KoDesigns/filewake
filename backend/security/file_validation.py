from __future__ import annotations

from pathlib import Path

from backend.conversion.registry import registry
from backend.errors import ConverterError
from backend.security.mime_detection import Detection, detect_file


def validate_input(path: Path, original_name: str | None, provided_mime: str | None = None) -> Detection:
    detection = detect_file(path, original_name, provided_mime)
    if not detection.format or not registry.is_input_format(detection.format):
        raise ConverterError(
            "unsupported_file",
            "The uploaded file type is not supported.",
            415,
        )
    return detection


def validate_output(path: Path, requested_format: str, max_bytes: int) -> int:
    if not path.is_file():
        raise ConverterError("conversion_failed", "The converter produced no output.", 422)
    size = path.stat().st_size
    if size == 0:
        raise ConverterError("conversion_failed", "The converter produced an empty file.", 422)
    if size > max_bytes:
        raise ConverterError(
            "output_too_large",
            "The converted file exceeds the configured output limit.",
            413,
        )
    detection = detect_file(path, path.name)
    equivalent = {
        "jpg": {"jpg"},
        "m4a": {"m4a", "mp4"},
        "aac": {"aac", "m4a"},
        "ogg": {"ogg", "opus"},
        "opus": {"opus", "ogg"},
        "md": {"md", "txt"},
    }
    accepted = equivalent.get(requested_format, {requested_format})
    if detection.format not in accepted:
        raise ConverterError(
            "conversion_failed",
            "The converter output did not match the requested format.",
            422,
        )
    return size
