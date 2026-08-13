from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from backend.config import Settings


def _validated_root(settings: Settings) -> Path:
    root = settings.workspace_root.resolve()
    temporary_roots = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve()}
    is_dedicated_temporary_path = any(
        root != temporary_root and root.is_relative_to(temporary_root)
        for temporary_root in temporary_roots
    )
    if not is_dedicated_temporary_path:
        raise RuntimeError("WORKSPACE_ROOT must be a dedicated directory below the system temporary directory")
    return root


class Workspace:
    def __init__(self, settings: Settings) -> None:
        root = _validated_root(settings)
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._temporary = tempfile.TemporaryDirectory(prefix="job-", dir=root)
        self.path = Path(self._temporary.name)
        self.home = self.path / "home"
        self.tmp = self.path / "tmp"
        self.libreoffice_profile = self.path / "libreoffice-profile"
        for directory in (self.home, self.tmp, self.libreoffice_profile):
            directory.mkdir(mode=0o700)

    def input_path(self, file_format: str) -> Path:
        return self.path / f"input.{file_format}"

    def output_path(self, file_format: str) -> Path:
        return self.path / f"output.{file_format}"

    def cleanup(self) -> None:
        self._temporary.cleanup()

    def __enter__(self) -> "Workspace":
        return self

    def __exit__(self, *_args) -> None:
        self.cleanup()


def cleanup_stale_workspaces(settings: Settings) -> None:
    root = _validated_root(settings)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    for child in root.iterdir():
        if child.is_dir() and not child.is_symlink() and child.name.startswith("job-"):
            shutil.rmtree(child, ignore_errors=True)
