from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ConversionResult:
    path: Path
    engine: str


class Converter:
    category: str

    def supports(self, input_format: str, output_format: str) -> bool:
        raise NotImplementedError

    def inspect(self, input_path: Path) -> dict:
        return {}

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        input_format: str,
        output_format: str,
        workspace: Path,
    ) -> ConversionResult:
        raise NotImplementedError
