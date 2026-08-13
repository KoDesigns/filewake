from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ConverterError(Exception):
    code: str
    message: str
    status_code: int = 400

    def __str__(self) -> str:
        return self.message


class ConversionTimeout(ConverterError):
    def __init__(self, message: str = "The conversion exceeded its time limit.") -> None:
        super().__init__("conversion_timeout", message, 408)


class ConversionFailed(ConverterError):
    def __init__(self, message: str = "The converter could not process this file.") -> None:
        super().__init__("conversion_failed", message, 422)
