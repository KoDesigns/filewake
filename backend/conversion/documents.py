from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree

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
    # UTF-8, comma field separator, double-quote text delimiter, first sheet only.
    "csv": "csv:Text - txt - csv (StarCalc):44,34,76,1,,0,false,true,true,false,false,0,false,false,false",
}

CSV_INPUT_FILTER = "Text - txt - csv (StarCalc):44,34,76,1,,0,false,true,true,false,false,0,false,false,false"

PANDOC_INPUTS = {"md": "commonmark", "txt": "commonmark", "html": "html", "epub": "epub"}
PANDOC_OUTPUTS = {"md": "commonmark", "html": "html5", "docx": "docx", "epub": "epub3"}
PANDOC_REFERENCE_DOCX = Path("/opt/filewake/pandoc-reference.docx")
EPUB_CONTAINER_PATH = "META-INF/container.xml"
EPUB_CONTAINER_NAMESPACE = "urn:oasis:names:tc:opendocument:xmlns:container"
EPUB_PACKAGE_NAMESPACE = "http://www.idpf.org/2007/opf"


class DocumentConverter(Converter):
    category = "document"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def supports(self, input_format: str, output_format: str) -> bool:
        spec = registry.get(input_format, output_format)
        return bool(spec and spec.category == self.category)

    def _libreoffice(
        self, input_path: Path, output_path: Path, input_format: str, output_format: str, workspace: Path
    ) -> None:
        output_dir = workspace / "lo-output"
        output_dir.mkdir(mode=0o700, exist_ok=True)
        profile_uri = f"file://{quote(str(workspace / 'libreoffice-profile'))}"
        arguments = [
            "libreoffice", "--headless", "--safe-mode", "--nologo", "--nodefault",
            "--nofirststartwizard", f"-env:UserInstallation={profile_uri}",
        ]
        if input_format == "csv":
            arguments.append(f"--infilter={CSV_INPUT_FILTER}")
        arguments.extend([
            "--convert-to", LIBREOFFICE_FILTERS[output_format],
            "--outdir", str(output_dir), str(input_path),
        ])
        run_command(
            arguments,
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
        pandoc_input = self._normalize_epub_for_pandoc(input_path, workspace) if input_format == "epub" else input_path
        arguments = [
            "pandoc", "--sandbox", "--from", PANDOC_INPUTS[input_format],
            "--to", PANDOC_OUTPUTS[output_format],
        ]
        if output_format == "docx" and PANDOC_REFERENCE_DOCX.is_file():
            # Debian's Pandoc cannot load its packaged DOCX data while sandboxed.
            # An explicit reference document remains readable without relaxing
            # the sandbox around untrusted uploaded content.
            arguments.append(f"--reference-doc={PANDOC_REFERENCE_DOCX}")
        if output_format == "html":
            # A fragment is detected as plain text by output validation, and any
            # extracted EPUB media would disappear with the temporary workspace.
            arguments.extend(["--standalone", "--embed-resources"])
        arguments.extend(["--output", str(output_path), str(pandoc_input)])
        run_command(
            arguments,
            self.settings.document_timeout_seconds,
            workspace,
            minimal_environment(workspace),
        )

    def _normalize_epub_for_pandoc(self, input_path: Path, workspace: Path) -> Path:
        """Remove dangling EPUB spine entries that make Pandoc abort with parseSpine."""
        try:
            with zipfile.ZipFile(input_path) as source:
                container = ElementTree.fromstring(source.read(EPUB_CONTAINER_PATH))
                rootfile = container.find(f".//{{{EPUB_CONTAINER_NAMESPACE}}}rootfile")
                package_path = rootfile.get("full-path") if rootfile is not None else None
                if not package_path or package_path not in source.namelist():
                    return input_path

                package = ElementTree.fromstring(source.read(package_path))
                namespace = f"{{{EPUB_PACKAGE_NAMESPACE}}}"
                manifest = package.find(f"{namespace}manifest")
                spine = package.find(f"{namespace}spine")
                if manifest is None or spine is None:
                    return input_path
                manifest_ids = {
                    item_id
                    for item in manifest.findall(f"{namespace}item")
                    if (item_id := item.get("id"))
                }
                dangling = [
                    itemref
                    for itemref in spine.findall(f"{namespace}itemref")
                    if itemref.get("idref") not in manifest_ids
                ]
                if not dangling:
                    return input_path
                for itemref in dangling:
                    spine.remove(itemref)

                ElementTree.register_namespace("", EPUB_PACKAGE_NAMESPACE)
                normalized_package = ElementTree.tostring(
                    package,
                    encoding="utf-8",
                    xml_declaration=True,
                )
                normalized_path = workspace / "pandoc-input.epub"
                with zipfile.ZipFile(normalized_path, "w", allowZip64=True) as destination:
                    for info in source.infolist():
                        if info.filename == package_path:
                            destination.writestr(info, normalized_package)
                            continue
                        with source.open(info) as reader, destination.open(info, "w") as writer:
                            shutil.copyfileobj(reader, writer)
                return normalized_path
        except (OSError, KeyError, ValueError, zipfile.BadZipFile, ElementTree.ParseError):
            # Pandoc remains the authority for other malformed-EPUB errors.
            return input_path

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
            self._libreoffice(input_path, output_path, input_format, output_format, workspace)
            return ConversionResult(output_path, "libreoffice")
        if output_format == "pdf":
            intermediate = workspace / "pandoc-output.docx"
            self._pandoc(input_path, intermediate, input_format, "docx", workspace)
            self._libreoffice(intermediate, output_path, "docx", "pdf", workspace)
            return ConversionResult(output_path, "pandoc+libreoffice")
        self._pandoc(input_path, output_path, input_format, output_format, workspace)
        return ConversionResult(output_path, "pandoc")
