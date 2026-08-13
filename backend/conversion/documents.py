from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from backend.config import Settings
from backend.conversion.base import ConversionResult, Converter
from backend.conversion.registry import registry
from backend.errors import ConversionFailed
from backend.runtime.subprocess import minimal_environment, run_command


LIBREOFFICE_FILTERS = {
    "pdf": "pdf",
    "docx": "docx:Office Open XML Text",
    "odt": "odt:writer8",
    "pptx": "pptx:Impress MS PowerPoint 2007 XML",
    "odp": "odp:impress8",
    "xlsx": "xlsx:Calc MS Excel 2007 XML",
    "ods": "ods:calc8",
}

PANDOC_INPUTS = {"md": "commonmark", "txt": "commonmark", "html": "html", "epub": "epub"}
PANDOC_OUTPUTS = {"md": "commonmark", "html": "html5", "docx": "docx", "epub": "epub3"}


class DocumentConverter(Converter):
    category = "document"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def supports(self, input_format: str, output_format: str) -> bool:
        spec = registry.get(input_format, output_format)
        return bool(spec and spec.category == self.category)

    def _libreoffice(
        self, input_path: Path, output_path: Path, output_format: str, workspace: Path
    ) -> None:
        output_dir = workspace / "lo-output"
        output_dir.mkdir(mode=0o700, exist_ok=True)
        profile_uri = f"file://{quote(str(workspace / 'libreoffice-profile'))}"
        run_command(
            [
                "libreoffice", "--headless", "--safe-mode", "--nologo", "--nodefault",
                "--nofirststartwizard", f"-env:UserInstallation={profile_uri}",
                "--convert-to", LIBREOFFICE_FILTERS[output_format],
                "--outdir", str(output_dir), str(input_path),
            ],
            self.settings.document_timeout_seconds,
            workspace,
            minimal_environment(workspace),
        )
        candidates = list(output_dir.glob(f"*.{output_format}"))
        if len(candidates) != 1:
            raise ConversionFailed()
        candidates[0].replace(output_path)

    def _pandoc(
        self, input_path: Path, output_path: Path, input_format: str, output_format: str, workspace: Path
    ) -> None:
        run_command(
            [
                "pandoc", "--sandbox", "--from", PANDOC_INPUTS[input_format],
                "--to", PANDOC_OUTPUTS[output_format], "--output", str(output_path),
                str(input_path),
            ],
            self.settings.document_timeout_seconds,
            workspace,
            minimal_environment(workspace),
        )

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        input_format: str,
        output_format: str,
        workspace: Path,
    ) -> ConversionResult:
        spec = registry.require(input_format, output_format)
        if spec.engine == "libreoffice":
            self._libreoffice(input_path, output_path, output_format, workspace)
            return ConversionResult(output_path, "libreoffice")
        if output_format == "pdf":
            intermediate = workspace / "pandoc-output.docx"
            self._pandoc(input_path, intermediate, input_format, "docx", workspace)
            self._libreoffice(intermediate, output_path, "pdf", workspace)
            return ConversionResult(output_path, "pandoc+libreoffice")
        self._pandoc(input_path, output_path, input_format, output_format, workspace)
        return ConversionResult(output_path, "pandoc")
