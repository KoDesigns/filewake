from __future__ import annotations

from pathlib import Path
import sys

from backend.config import Settings
from backend.conversion.base import ConversionResult, Converter
from backend.conversion.registry import registry
from backend.runtime.subprocess import minimal_environment, run_command


class FontConverter(Converter):
    category = "font"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def supports(self, input_format: str, output_format: str) -> bool:
        spec = registry.get(input_format, output_format)
        return bool(spec and spec.category == self.category)

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        input_format: str,
        output_format: str,
        workspace: Path,
    ) -> ConversionResult:
        run_command(
            [
                sys.executable, "-I", str(Path(__file__).with_name("font_worker.py")),
                str(input_path), str(output_path), output_format,
            ],
            self.settings.font_timeout_seconds,
            workspace,
            minimal_environment(workspace),
        )
        return ConversionResult(output_path, "fonttools")
