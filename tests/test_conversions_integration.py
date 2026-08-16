from __future__ import annotations

import base64
import wave
from pathlib import Path

import pytest

from backend.config import Settings
from backend.conversion.dispatcher import Dispatcher
from backend.runtime.subprocess import converter_executable, minimal_environment, run_command
from backend.runtime.workspace import Workspace
from backend.security.file_validation import validate_output


pytestmark = pytest.mark.integration
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nWQAAAAASUVORK5CYII="
)


def settings_for(tmp_path: Path) -> Settings:
    return Settings(workspace_root=tmp_path / "converter", max_output_size_mb=32)


def require_tools(*names: str) -> None:
    missing = [name for name in names if converter_executable(name) is None]
    if missing:
        pytest.skip(f"missing production engines: {', '.join(missing)}")


def test_png_to_jpg_and_cleanup(tmp_path):
    require_tools("vips", "vipsheader")
    settings = settings_for(tmp_path)
    job_path = None
    with Workspace(settings) as workspace:
        job_path = workspace.path
        source = workspace.input_path("png")
        destination = workspace.output_path("jpg")
        source.write_bytes(PNG_1X1)
        result = Dispatcher(settings).convert(source, destination, "png", "jpg", workspace.path)
        assert result.engine == "libvips"
        assert validate_output(destination, "jpg", settings.max_output_size_bytes) > 0
    assert job_path is not None and not job_path.exists()


def test_three_band_rgb_png_to_jpg(tmp_path):
    require_tools("vips", "vipsheader")
    settings = settings_for(tmp_path)
    with Workspace(settings) as workspace:
        source = workspace.input_path("png")
        run_command(
            ["vips", "black", str(source), "32", "24", "--bands", "3"],
            timeout=30,
            cwd=workspace.path,
            env=minimal_environment(workspace.path),
        )
        destination = workspace.output_path("jpg")
        result = Dispatcher(settings).convert(source, destination, "png", "jpg", workspace.path)
        assert result.engine == "libvips"
        assert validate_output(destination, "jpg", settings.max_output_size_bytes) > 0


def test_imagemagick_policy_allows_v1_raster_conversion(tmp_path):
    require_tools("vips", "magick")
    settings = settings_for(tmp_path)
    with Workspace(settings) as workspace:
        source = workspace.input_path("png")
        run_command(
            ["vips", "black", str(source), "16", "16", "--bands", "3"],
            timeout=30,
            cwd=workspace.path,
            env=minimal_environment(workspace.path),
        )
        destination = workspace.output_path("jpg")
        run_command(
            ["magick", str(source), "-auto-orient", "-strip", str(destination)],
            timeout=30,
            cwd=workspace.path,
            env=minimal_environment(workspace.path),
        )
        assert validate_output(destination, "jpg", settings.max_output_size_bytes) > 0


def test_wav_to_mp3(tmp_path):
    require_tools("ffmpeg")
    settings = settings_for(tmp_path)
    with Workspace(settings) as workspace:
        source = workspace.input_path("wav")
        with wave.open(str(source), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8_000)
            audio.writeframes(b"\x00\x00" * 8_000)
        destination = workspace.output_path("mp3")
        Dispatcher(settings).convert(source, destination, "wav", "mp3", workspace.path)
        assert validate_output(destination, "mp3", settings.max_output_size_bytes) > 0


def test_h264_aac_mkv_to_mp4_remux(tmp_path):
    require_tools("ffmpeg", "ffprobe")
    settings = settings_for(tmp_path)
    with Workspace(settings) as workspace:
        source = workspace.input_path("mkv")
        run_command(
            [
                "ffmpeg", "-nostdin", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
                "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono", "-shortest",
                "-c:v", "libx264", "-c:a", "aac", "-y", str(source),
            ],
            timeout=30,
            cwd=workspace.path,
            env=minimal_environment(workspace.path),
        )
        destination = workspace.output_path("mp4")
        result = Dispatcher(settings).convert(source, destination, "mkv", "mp4", workspace.path)
        assert result.engine == "ffmpeg-remux"
        assert validate_output(destination, "mp4", settings.max_output_size_bytes) > 0


def test_video_to_mp3_extracts_audio_track(tmp_path):
    require_tools("ffmpeg", "ffprobe")
    settings = settings_for(tmp_path)
    with Workspace(settings) as workspace:
        source = workspace.input_path("mp4")
        run_command(
            [
                "ffmpeg", "-nostdin", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=1",
                "-shortest", "-c:v", "libx264", "-c:a", "aac", "-y", str(source),
            ],
            timeout=30,
            cwd=workspace.path,
            env=minimal_environment(workspace.path),
        )
        destination = workspace.output_path("mp3")
        result = Dispatcher(settings).convert(source, destination, "mp4", "mp3", workspace.path)
        assert result.engine == "ffmpeg"
        assert validate_output(destination, "mp3", settings.max_output_size_bytes) > 0


def test_markdown_to_html(tmp_path):
    require_tools("pandoc")
    settings = settings_for(tmp_path)
    with Workspace(settings) as workspace:
        source = workspace.input_path("md")
        source.write_text("# Private conversion\n\nLocal bytes only.\n", encoding="utf-8")
        destination = workspace.output_path("html")
        Dispatcher(settings).convert(source, destination, "md", "html", workspace.path)
        assert "Private conversion" in destination.read_text(encoding="utf-8")


def test_docx_to_pdf(tmp_path):
    require_tools("pandoc", "libreoffice")
    settings = settings_for(tmp_path)
    with Workspace(settings) as workspace:
        markdown = workspace.input_path("md")
        docx = workspace.path / "input.docx"
        markdown.write_text("# Office conversion\n", encoding="utf-8")
        Dispatcher(settings).convert(markdown, docx, "md", "docx", workspace.path)
        destination = workspace.output_path("pdf")
        Dispatcher(settings).convert(docx, destination, "docx", "pdf", workspace.path)
        assert validate_output(destination, "pdf", settings.max_output_size_bytes) > 0


def test_csv_to_xlsx_and_back(tmp_path):
    require_tools("libreoffice")
    settings = settings_for(tmp_path)
    with Workspace(settings) as workspace:
        source = workspace.input_path("csv")
        source.write_text('name,amount,formula\n"North wave",42,"=1+1"\n', encoding="utf-8")
        workbook = workspace.output_path("xlsx")
        result = Dispatcher(settings).convert(source, workbook, "csv", "xlsx", workspace.path)
        assert result.engine == "libreoffice"
        assert validate_output(workbook, "xlsx", settings.max_output_size_bytes) > 0

        restored = workspace.path / "restored.csv"
        Dispatcher(settings).convert(workbook, restored, "xlsx", "csv", workspace.path)
        assert validate_output(restored, "csv", settings.max_output_size_bytes) > 0
        exported = restored.read_text(encoding="utf-8")
        assert "North wave" in exported
        assert "=1+1" in exported


def test_ttf_to_woff2_and_back(tmp_path):
    font = next(
        (
            candidate
            for candidate in (
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                Path("/System/Library/Fonts/Supplemental/Georgia.ttf"),
            )
            if candidate.is_file()
        ),
        None,
    )
    if font is None:
        pytest.skip("production test font is unavailable")
    settings = settings_for(tmp_path)
    with Workspace(settings) as workspace:
        source = workspace.input_path("ttf")
        source.write_bytes(font.read_bytes())
        webfont = workspace.output_path("woff2")
        Dispatcher(settings).convert(source, webfont, "ttf", "woff2", workspace.path)
        assert validate_output(webfont, "woff2", settings.max_output_size_bytes) > 0
        restored = workspace.path / "restored.ttf"
        Dispatcher(settings).convert(webfont, restored, "woff2", "ttf", workspace.path)
        assert validate_output(restored, "ttf", settings.max_output_size_bytes) > 0
