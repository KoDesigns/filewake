from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_name: str = "Filewake"
    app_version: str = "1.0.0"
    workspace_root: Path = Path("/tmp/converter")

    max_file_size_mb: int = Field(default=2048, ge=1)
    max_batch_files: int = Field(default=50, ge=1, le=500)
    max_batch_size_mb: int = Field(default=4096, ge=1)
    max_parallel_conversions: int = Field(default=2, ge=1, le=32)
    max_image_pixels: int = Field(default=100_000_000, ge=1_000_000)
    max_output_size_mb: int = Field(default=4096, ge=1)

    image_timeout_seconds: int = Field(default=120, ge=1)
    font_timeout_seconds: int = Field(default=120, ge=1)
    document_timeout_seconds: int = Field(default=300, ge=1)
    audio_timeout_seconds: int = Field(default=600, ge=1)
    video_timeout_seconds: int = Field(default=1800, ge=1)

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def max_request_size_bytes(self) -> int:
        # Multipart headers and the single output-format field need a small allowance.
        return self.max_file_size_bytes + 1024 * 1024

    @property
    def max_output_size_bytes(self) -> int:
        return self.max_output_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
