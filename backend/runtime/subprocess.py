from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from backend.errors import ConversionFailed, ConversionTimeout


MAX_CAPTURE_BYTES = 64 * 1024
CONVERTER_PATH = ":".join(
    (
        "/opt/imagemagick/bin",
        "/opt/ffmpeg/bin",
        "/opt/vips/bin",
        "/opt/homebrew/bin",
        "/opt/homebrew/sbin",
        "/Applications/LibreOffice.app/Contents/MacOS",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
    )
)


def converter_executable(name: str, path: str = CONVERTER_PATH) -> str | None:
    candidates = ("libreoffice", "soffice") if name == "libreoffice" else (name,)
    for candidate in candidates:
        if executable := shutil.which(candidate, path=path):
            return executable
    return None


def _imagemagick_config_path() -> str:
    container_config = Path("/etc/ImageMagick-7")
    if (container_config / "policy.xml").is_file():
        return str(container_config)
    return str(Path(__file__).resolve().parents[2] / "config")


@dataclass(frozen=True, slots=True)
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


def minimal_environment(workspace: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    environment = {
        "PATH": CONVERTER_PATH,
        "HOME": str(workspace / "home"),
        "TMPDIR": str(workspace / "tmp"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "MAGICK_CONFIGURE_PATH": _imagemagick_config_path(),
    }
    if extra:
        environment.update(extra)
    return environment


def run_command(
    args: list[str],
    timeout: int,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> CommandResult:
    if not args or not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise ValueError("args must be a non-empty list of strings")
    executable = converter_executable(args[0], path=(env or {}).get("PATH", CONVERTER_PATH))
    if executable is None:
        raise ConversionFailed(f"Required conversion engine '{args[0]}' is unavailable.")
    command = [executable, *args[1:]]
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env or minimal_environment(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        shell=False,
        start_new_session=True,
    )
    stdout_buffer = bytearray()
    stderr_buffer = bytearray()

    def drain(stream, buffer: bytearray) -> None:
        while chunk := stream.read(8192):
            buffer.extend(chunk)
            if len(buffer) > MAX_CAPTURE_BYTES:
                del buffer[:-MAX_CAPTURE_BYTES]

    readers = [
        threading.Thread(target=drain, args=(process.stdout, stdout_buffer), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, stderr_buffer), daemon=True),
    ]
    for reader in readers:
        reader.start()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        for reader in readers:
            reader.join(timeout=2)
        raise ConversionTimeout() from exc
    for reader in readers:
        reader.join(timeout=2)
    if process.returncode != 0:
        raise ConversionFailed()
    return CommandResult(
        stdout=stdout_buffer.decode("utf-8", errors="replace"),
        stderr=stderr_buffer.decode("utf-8", errors="replace"),
        returncode=process.returncode,
    )
