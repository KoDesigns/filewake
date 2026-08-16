from __future__ import annotations

import json
from pathlib import Path

from backend.config import Settings
from backend.conversion.audio import AUDIO_ENCODERS
from backend.conversion.base import ConversionResult, Converter
from backend.conversion.registry import AUDIO_FORMATS, registry
from backend.errors import ConverterError
from backend.runtime.subprocess import minimal_environment, run_command


CONTAINER_CODECS = {
    "mp4": {"video": {"h264", "hevc", "av1", "mpeg4"}, "audio": {"aac", "mp3", "alac", "ac3"}},
    "mov": {"video": {"h264", "hevc", "prores", "mpeg4"}, "audio": {"aac", "alac", "pcm_s16le", "pcm_s24le"}},
    "webm": {"video": {"vp8", "vp9", "av1"}, "audio": {"opus", "vorbis"}},
    "mkv": {"video": {"h264", "hevc", "vp8", "vp9", "av1", "mpeg4", "prores"}, "audio": {"aac", "mp3", "opus", "vorbis", "flac", "ac3"}},
}


class VideoConverter(Converter):
    category = "video"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def supports(self, input_format: str, output_format: str) -> bool:
        spec = registry.get(input_format, output_format)
        return bool(spec and spec.category == self.category)

    def inspect(self, input_path: Path) -> dict:
        result = run_command(
            [
                "ffprobe", "-v", "error", "-show_streams", "-show_format",
                "-of", "json", "-protocol_whitelist", "file,pipe", str(input_path),
            ],
            min(self.settings.video_timeout_seconds, 60),
            input_path.parent,
            minimal_environment(input_path.parent),
        )
        try:
            probe = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ConverterError("invalid_file", "Media stream metadata is invalid.", 422) from exc
        streams = probe.get("streams", [])
        if not any(stream.get("codec_type") == "video" for stream in streams):
            raise ConverterError("invalid_file", "The uploaded container has no video stream.", 422)
        return probe

    @staticmethod
    def _can_remux(probe: dict, target: str) -> bool:
        allowed = CONTAINER_CODECS[target]
        relevant = [stream for stream in probe.get("streams", []) if stream.get("codec_type") in {"video", "audio"}]
        return bool(relevant) and all(
            stream.get("codec_name") in allowed[stream["codec_type"]] for stream in relevant
        )

    @staticmethod
    def _transcode_args(target: str) -> list[str]:
        if target in {"mp4", "mov"}:
            return [
                "-c:v", "libx264", "-preset", "medium", "-crf", "21",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
            ]
        if target == "webm":
            return [
                "-c:v", "libvpx-vp9", "-crf", "31", "-b:v", "0",
                "-cpu-used", "2", "-c:a", "libopus", "-b:a", "160k",
            ]
        return [
            "-c:v", "libx264", "-preset", "medium", "-crf", "21",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        ]

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        input_format: str,
        output_format: str,
        workspace: Path,
    ) -> ConversionResult:
        probe = self.inspect(input_path)
        if output_format in AUDIO_FORMATS:
            if not any(stream.get("codec_type") == "audio" for stream in probe.get("streams", [])):
                raise ConverterError("conversion_failed", "The uploaded video has no audio track.", 422)
            args = [
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-protocol_whitelist", "file,pipe", "-i", str(input_path),
                "-map", "0:a:0", "-map_metadata", "0", "-vn",
                *AUDIO_ENCODERS[output_format], "-y", str(output_path),
            ]
            run_command(
                args,
                self.settings.video_timeout_seconds,
                workspace,
                minimal_environment(workspace),
            )
            return ConversionResult(output_path, "ffmpeg")

        remux = self._can_remux(probe, output_format)
        codec_args = ["-c", "copy"] if remux else self._transcode_args(output_format)
        args = [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-protocol_whitelist", "file,pipe", "-i", str(input_path),
            "-map", "0:v:0", "-map", "0:a:0?", "-map_metadata", "0",
            *codec_args, "-y", str(output_path),
        ]
        run_command(
            args,
            self.settings.video_timeout_seconds,
            workspace,
            minimal_environment(workspace),
        )
        return ConversionResult(output_path, "ffmpeg-remux" if remux else "ffmpeg")
