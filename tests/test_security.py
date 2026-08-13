from __future__ import annotations

import base64
import time
import sys
from pathlib import Path

import pytest

from backend.errors import ConversionFailed, ConversionTimeout
from backend.runtime.subprocess import CONVERTER_PATH, minimal_environment, run_command
from backend.runtime.workspace import Workspace
from backend.security.filenames import safe_download_name
from backend.security.mime_detection import detect_file


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nWQAAAAASUVORK5CYII="
)


@pytest.mark.parametrize(
    "hostile",
    ["../../etc/passwd", '"; rm -rf /"', "$(touch /tmp/test)", "photo.jpg;curl attacker"],
)
def test_hostile_names_are_display_metadata(hostile):
    result = safe_download_name(hostile, "png")
    assert "/" not in result
    assert "\\" not in result
    assert ";" not in result
    assert "$" not in result
    assert result.endswith(".png")


def test_shell_metacharacters_are_not_evaluated(tmp_path):
    marker = tmp_path / "owned"
    value = f"$(touch {marker})"
    result = run_command(
        ["/bin/echo", value],
        timeout=2,
        cwd=tmp_path,
        env=minimal_environment(tmp_path),
    )
    assert value in result.stdout
    assert not marker.exists()


def test_converter_environment_supports_apple_silicon_without_inheriting_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("PRIVATE_API_TOKEN", "do-not-pass")
    environment = minimal_environment(tmp_path)
    assert "/opt/homebrew/bin" in CONVERTER_PATH
    assert environment["PATH"] == CONVERTER_PATH
    assert environment["MAGICK_CONFIGURE_PATH"].endswith(("/config", "/ImageMagick-7"))
    assert "PRIVATE_API_TOKEN" not in environment


def test_command_timeout_kills_process_group(tmp_path):
    started = time.monotonic()
    with pytest.raises(ConversionTimeout):
        run_command(
            ["/bin/sleep", "10"],
            timeout=1,
            cwd=tmp_path,
            env=minimal_environment(tmp_path),
        )
    assert time.monotonic() - started < 5


def test_command_failure_hides_stderr(tmp_path):
    with pytest.raises(ConversionFailed) as exc:
        run_command(
            ["/bin/sh", "-c", "echo secret >&2; exit 2"],
            timeout=2,
            cwd=tmp_path,
            env=minimal_environment(tmp_path),
        )
    assert "secret" not in str(exc.value)


def test_command_output_capture_is_bounded(tmp_path):
    result = run_command(
        [sys.executable, "-c", "import sys; sys.stdout.write('x' * 131072)"],
        timeout=2,
        cwd=tmp_path,
        env=minimal_environment(tmp_path),
    )
    assert len(result.stdout.encode()) <= 64 * 1024


def test_workspace_cleanup_on_exception(monkeypatch, tmp_path):
    from backend.config import Settings

    settings = Settings(workspace_root=tmp_path / "converter")
    path: Path | None = None
    with pytest.raises(RuntimeError):
        with Workspace(settings) as workspace:
            path = workspace.path
            raise RuntimeError("stop")
    assert path is not None and not path.exists()


def test_documented_tmp_workspace_root_is_accepted():
    from backend.config import Settings

    settings = Settings(workspace_root=Path("/tmp/converter-test"))
    with Workspace(settings) as workspace:
        path = workspace.path
        assert path.is_dir()
    assert not path.exists()


def test_png_named_docx_is_detected_as_png(tmp_path):
    path = tmp_path / "input.bin"
    path.write_bytes(PNG_1X1)
    detection = detect_file(path, "document.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert detection.format == "png"
    assert detection.mismatch is True
    assert detection.mime_mismatch is True


def test_random_bytes_named_video_are_not_trusted(tmp_path):
    path = tmp_path / "input.bin"
    path.write_bytes(b"not a real media file\x00\xff")
    detection = detect_file(path, "video.mp4")
    assert detection.format is None


def test_oversized_content_length_rejected_before_parsing(client):
    response = client.post(
        "/api/inspect",
        headers={"content-type": "multipart/form-data; boundary=x", "content-length": str(2 * 1024 * 1024 + 1)},
        content=b"",
    )
    assert response.status_code == 413
    assert response.json()["error"] == "file_too_large"


def test_designspace_is_rejected(client, workspace_root):
    response = client.post(
        "/api/inspect",
        files={"file": ("malicious.designspace", b"<?xml version='1.0'?><designspace/>", "application/xml")},
    )
    assert response.status_code == 415
    assert response.json()["error"] == "unsupported_file"
    assert not list(workspace_root.glob("job-*"))


def test_malformed_file_cleanup(client, workspace_root):
    response = client.post(
        "/api/inspect",
        files={"file": ("video.mp4", b"not an mp4", "video/mp4")},
    )
    assert response.status_code == 415
    assert not list(workspace_root.glob("job-*"))
