from __future__ import annotations

from pathlib import Path

from backend.config import Settings
from backend.conversion.audio import AudioConverter
from backend.conversion.base import ConversionResult, Converter
from backend.conversion.documents import DocumentConverter
from backend.conversion.fonts import FontConverter
from backend.conversion.images import ImageConverter
from backend.conversion.registry import registry
from backend.conversion.video import VideoConverter
from backend.errors import ConverterError


class Dispatcher:
    def __init__(self, settings: Settings) -> None:
        self.converters: dict[str, Converter] = {
            "image": ImageConverter(settings),
            "audio": AudioConverter(settings),
            "video": VideoConverter(settings),
            "document": DocumentConverter(settings),
            "font": FontConverter(settings),
        }

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        input_format: str,
        output_format: str,
        workspace: Path,
    ) -> ConversionResult:
        spec = registry.require(input_format, output_format)
        converter = self.converters[spec.category]
        if not converter.supports(input_format, output_format):
            raise ConverterError("unsupported_conversion", "This conversion is not supported.", 422)
        return converter.convert(input_path, output_path, input_format, output_format, workspace)

    def inspect(self, input_path: Path, category: str) -> dict:
        return self.converters[category].inspect(input_path)
