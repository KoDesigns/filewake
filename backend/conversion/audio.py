from __future__ import annotations

from pathlib import Path

from backend.config import Settings
from backend.conversion.base import ConversionResult, Converter
from backend.conversion.registry import registry
from backend.runtime.subprocess import minimal_environment, run_command


AUDIO_ENCODERS = {
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    "wav": ["-c:a", "pcm_s16le"],
    "flac": ["-c:a", "flac", "-compression_level", "8"],
    "aac": ["-c:a", "aac", "-b:a", "224k"],
    "m4a": ["-c:a", "aac", "-b:a", "224k"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "6"],
    "opus": ["-c:a", "libopus", "-b:a", "160k", "-vbr", "on"],
    "aiff": ["-c:a", "pcm_s16be"],
}


class AudioConverter(Converter):
    category = "audio"

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
        args = [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-protocol_whitelist", "file,pipe", "-i", str(input_path),
            "-map", "0:a:0", "-map_metadata", "0", "-vn",
            *AUDIO_ENCODERS[output_format], "-y", str(output_path),
        ]
        run_command(
            args,
            self.settings.audio_timeout_seconds,
            workspace,
            minimal_environment(workspace),
        )
        return ConversionResult(output_path, "ffmpeg")
