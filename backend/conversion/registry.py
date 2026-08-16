from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ConversionSpec:
    input: str
    output: str
    category: str
    engine: str
    input_mime: str
    output_mime: str
    default: bool = False


MIMES = {
    "jpg": "image/jpeg", "png": "image/png", "webp": "image/webp",
    "avif": "image/avif", "heic": "image/heic", "tiff": "image/tiff",
    "mp3": "audio/mpeg", "wav": "audio/wav", "flac": "audio/flac",
    "aac": "audio/aac", "m4a": "audio/mp4", "ogg": "audio/ogg",
    "opus": "audio/ogg", "aiff": "audio/aiff",
    "mp4": "video/mp4", "mkv": "video/x-matroska", "mov": "video/quicktime",
    "webm": "video/webm",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "odt": "application/vnd.oasis.opendocument.text", "rtf": "application/rtf",
    "txt": "text/plain", "md": "text/markdown", "html": "text/html",
    "epub": "application/epub+zip", "pdf": "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "odp": "application/vnd.oasis.opendocument.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "csv": "text/csv",
    "ttf": "font/ttf", "otf": "font/otf", "woff": "font/woff",
    "woff2": "font/woff2",
}

AUDIO_FORMATS = ["mp3", "wav", "flac", "aac", "m4a", "ogg", "opus", "aiff"]
VIDEO_FORMATS = ["mp4", "mkv", "mov", "webm"]

DEFAULTS = {
    "heic": "jpg", "tiff": "jpg", "png": "webp", "flac": "mp3",
    "wav": "mp3", "mov": "mp4", "mkv": "mp4", "docx": "pdf",
    "odt": "pdf", "pptx": "pdf", "xlsx": "pdf", "csv": "xlsx", "ttf": "woff2",
    "otf": "woff2", "woff": "ttf", "woff2": "ttf",
}


class ConversionRegistry:
    def __init__(self) -> None:
        self._specs: dict[tuple[str, str], ConversionSpec] = {}
        self._register_all()

    def _add(self, source: str, target: str, category: str, engine: str) -> None:
        self._specs[(source, target)] = ConversionSpec(
            input=source,
            output=target,
            category=category,
            engine=engine,
            input_mime=MIMES[source],
            output_mime=MIMES[target],
            default=DEFAULTS.get(source) == target,
        )

    def _register_all(self) -> None:
        image_inputs = ["jpg", "png", "webp", "avif", "heic", "tiff"]
        image_outputs = ["jpg", "png", "webp", "avif", "tiff"]
        for source in image_inputs:
            for target in image_outputs:
                if source != target:
                    self._add(source, target, "image", "libvips")

        for source in AUDIO_FORMATS:
            for target in AUDIO_FORMATS:
                if source != target:
                    self._add(source, target, "audio", "ffmpeg")

        for source in VIDEO_FORMATS:
            for target in [*VIDEO_FORMATS, *AUDIO_FORMATS]:
                if source != target:
                    self._add(source, target, "video", "ffmpeg")

        libreoffice = {
            "docx": ["pdf", "odt"], "odt": ["pdf", "docx"],
            "rtf": ["pdf", "docx"], "pptx": ["pdf", "odp"],
            "odp": ["pdf", "pptx"], "xlsx": ["pdf", "ods", "csv"],
            "ods": ["pdf", "xlsx"],
            "csv": ["xlsx"],
        }
        for source, targets in libreoffice.items():
            for target in targets:
                self._add(source, target, "document", "libreoffice")

        pandoc = {
            "md": ["html", "docx", "epub", "pdf"],
            "txt": ["html", "docx", "pdf"],
            "html": ["md", "docx"],
            "epub": ["html", "md"],
        }
        for source, targets in pandoc.items():
            for target in targets:
                self._add(source, target, "document", "pandoc")

        for source in ["ttf", "otf"]:
            for target in ["woff", "woff2"]:
                self._add(source, target, "font", "fonttools")
        for source in ["woff", "woff2"]:
            for target in ["ttf", "otf"]:
                self._add(source, target, "font", "fonttools")

    def get(self, source: str, target: str) -> ConversionSpec | None:
        return self._specs.get((source.lower(), target.lower()))

    def require(self, source: str, target: str) -> ConversionSpec:
        from backend.errors import ConverterError

        spec = self.get(source, target)
        if spec is None:
            raise ConverterError(
                "unsupported_conversion",
                f"Conversion from {source.upper()} to {target.upper()} is not supported.",
                422,
            )
        return spec

    def is_input_format(self, file_format: str) -> bool:
        return any(source == file_format for source, _ in self._specs)

    def possible_outputs(self, source: str) -> list[str]:
        specs = [spec for (item, _), spec in self._specs.items() if item == source]
        return [
            spec.output
            for spec in sorted(
                specs,
                key=lambda item: (
                    not item.default,
                    source in VIDEO_FORMATS and item.output in AUDIO_FORMATS,
                    item.output,
                ),
            )
        ]

    def default_output(self, source: str) -> str | None:
        return next((spec.output for spec in self._specs.values() if spec.input == source and spec.default), None)

    def categories(self) -> dict[str, dict[str, list[str]]]:
        result: dict[str, dict[str, list[str]]] = defaultdict(dict)
        sources = sorted({spec.input for spec in self._specs.values()})
        for source in sources:
            specs = [spec for spec in self._specs.values() if spec.input == source]
            if specs:
                result[specs[0].category][source] = self.possible_outputs(source)
        return dict(result)

    def specs(self) -> list[dict]:
        return [asdict(spec) for spec in sorted(self._specs.values(), key=lambda item: (item.category, item.input, item.output))]

    def category_for(self, source: str) -> str | None:
        return next((spec.category for spec in self._specs.values() if spec.input == source), None)


registry = ConversionRegistry()
