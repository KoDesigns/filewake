from __future__ import annotations

import mimetypes
import zipfile
from dataclasses import dataclass
from pathlib import Path

try:
    import magic
except ImportError:  # pragma: no cover - production image always includes libmagic
    magic = None


EXTENSION_ALIASES = {"jpeg": "jpg", "htm": "html", "markdown": "md", "heif": "heic"}

MIME_FORMATS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/avif": "avif",
    "image/heic": "heic",
    "image/heif": "heic",
    "image/tiff": "tiff",
    "image/bmp": "bmp",
    "image/gif": "gif",
    "image/vnd.microsoft.icon": "ico",
    "audio/mpeg": "mp3",
    "audio/x-wav": "wav",
    "audio/wav": "wav",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
    "audio/aac": "aac",
    "audio/ogg": "ogg",
    "audio/opus": "opus",
    "audio/x-aiff": "aiff",
    "audio/mp4": "m4a",
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/x-matroska": "mkv",
    "video/webm": "webm",
    "application/rtf": "rtf",
    "text/rtf": "rtf",
    "text/html": "html",
    "application/epub+zip": "epub",
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.oasis.opendocument.text": "odt",
    "application/vnd.oasis.opendocument.presentation": "odp",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
    "application/vnd.ms-fontobject": "woff",
    "font/woff": "woff",
    "font/woff2": "woff2",
    "font/ttf": "ttf",
    "font/otf": "otf",
}

OOXML_MARKERS = {
    "word/": "docx",
    "ppt/": "pptx",
    "xl/": "xlsx",
}

ODF_MIMES = {
    "application/vnd.oasis.opendocument.text": "odt",
    "application/vnd.oasis.opendocument.presentation": "odp",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
}


@dataclass(frozen=True, slots=True)
class Detection:
    format: str | None
    mime: str
    provided_mime: str | None
    extension_format: str | None
    mismatch: bool
    mime_mismatch: bool
    confidence: str


def normalize_extension(filename: str | None) -> str | None:
    extension = Path(filename or "").suffix.lower().lstrip(".")
    if not extension:
        return None
    return EXTENSION_ALIASES.get(extension, extension)


def _zip_format(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            name_set = set(names)
            if "mimetype" in name_set:
                with archive.open("mimetype") as mime_entry:
                    mime = mime_entry.read(128).decode("ascii", errors="ignore").strip()
                if mime == "application/epub+zip":
                    return "epub"
                if mime in ODF_MIMES:
                    return ODF_MIMES[mime]
            if "[Content_Types].xml" in name_set:
                for prefix, file_format in OOXML_MARKERS.items():
                    if any(name.startswith(prefix) for name in names):
                        return file_format
    except (OSError, zipfile.BadZipFile, KeyError):
        return None
    return None


def _signature_format(path: Path) -> str | None:
    try:
        with path.open("rb") as stream:
            header = stream.read(16)
    except OSError:
        return None
    if header.startswith(b"wOFF"):
        return "woff"
    if header.startswith(b"wOF2"):
        return "woff2"
    if header.startswith(b"OTTO"):
        return "otf"
    if header.startswith((b"\x00\x01\x00\x00", b"true")):
        return "ttf"
    return None


def _fallback_mime(path: Path) -> str:
    with path.open("rb") as stream:
        header = stream.read(512)
    signatures = (
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"\xff\xd8\xff", "image/jpeg"),
        (b"GIF8", "image/gif"),
        (b"%PDF-", "application/pdf"),
        (b"PK\x03\x04", "application/zip"),
        (b"fLaC", "audio/flac"),
        (b"OggS", "audio/ogg"),
        (b"ID3", "audio/mpeg"),
        (b"\x1aE\xdf\xa3", "video/x-matroska"),
    )
    for signature, mime in signatures:
        if header.startswith(signature):
            return mime
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "audio/wav"
    if header.lstrip().lower().startswith((b"<!doctype html", b"<html")):
        return "text/html"
    try:
        header.decode("utf-8")
        return "text/plain"
    except UnicodeDecodeError:
        return "application/octet-stream"


def _bmff_format(path: Path, extension: str | None) -> str | None:
    try:
        with path.open("rb") as stream:
            header = stream.read(32)
    except OSError:
        return None
    if len(header) < 12 or header[4:8] != b"ftyp":
        return None
    brands = {header[8:12], *(header[index:index + 4] for index in range(16, len(header), 4))}
    if brands & {b"avif", b"avis"}:
        return "avif"
    if brands & {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1"}:
        return "heic"
    if b"qt  " in brands:
        return "mov"
    if extension in {"mp4", "m4a"}:
        return extension
    return "mp4"


def font_desktop_format(path: Path) -> str | None:
    try:
        with path.open("rb") as stream:
            header = stream.read(8)
    except OSError:
        return None
    if header[:4] in {b"wOFF", b"wOF2"}:
        flavor = header[4:8]
        return "otf" if flavor == b"OTTO" else "ttf" if flavor in {b"\x00\x01\x00\x00", b"true"} else None
    return "otf" if header[:4] == b"OTTO" else "ttf" if header[:4] in {b"\x00\x01\x00\x00", b"true"} else None


def detect_file(
    path: Path,
    original_name: str | None = None,
    provided_mime: str | None = None,
) -> Detection:
    extension = normalize_extension(original_name)
    mime = magic.from_file(str(path), mime=True) if magic is not None else _fallback_mime(path)
    mime = mime or "application/octet-stream"
    detected = _signature_format(path) or MIME_FORMATS.get(mime)

    if mime in {"application/zip", "application/x-zip", "application/x-zip-compressed"}:
        detected = _zip_format(path)

    # libmagic often reports ISO-BMFF variants generically. The extension only
    # disambiguates formats sharing the same validated container signature.
    if mime in {"application/octet-stream", "video/mp4", "audio/mp4", "video/quicktime", "image/avif", "image/heic", "image/heif"}:
        bmff = _bmff_format(path, extension)
        if bmff:
            detected = bmff
        elif extension in {"mp4", "m4a", "mov", "avif", "heic"}:
            detected = None

    if mime == "text/plain" and extension in {"txt", "md"}:
        detected = extension

    if detected is None and extension == "rtf":
        with path.open("rb") as stream:
            if stream.read(5) == b"{\\rtf":
                detected = "rtf"
                mime = "application/rtf"

    guessed_mime = mimetypes.guess_type(f"file.{detected}")[0] if detected else None
    if mime == "application/octet-stream" and guessed_mime:
        mime = guessed_mime

    mismatch = extension is not None and detected is not None and extension != detected
    normalized_provided = provided_mime.lower().split(";", 1)[0].strip() if provided_mime else None
    mime_mismatch = bool(
        normalized_provided
        and normalized_provided != "application/octet-stream"
        and normalized_provided != mime
    )
    return Detection(
        format=detected,
        mime=mime,
        provided_mime=normalized_provided,
        extension_format=extension,
        mismatch=mismatch,
        mime_mismatch=mime_mismatch,
        confidence="high" if detected else "unknown",
    )
