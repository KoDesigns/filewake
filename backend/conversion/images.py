from __future__ import annotations

from pathlib import Path

from backend.config import Settings
from backend.conversion.base import ConversionResult, Converter
from backend.conversion.registry import registry
from backend.errors import ConversionFailed, ConverterError
from backend.runtime.subprocess import minimal_environment, run_command
from backend.security.image_dimensions import read_image_dimensions


class ImageConverter(Converter):
    category = "image"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def supports(self, input_format: str, output_format: str) -> bool:
        spec = registry.get(input_format, output_format)
        return bool(spec and spec.category == self.category)

    def inspect(self, input_path: Path) -> dict:
        dimensions = read_image_dimensions(input_path)
        if dimensions is None:
            env = minimal_environment(input_path.parent)
            width = run_command(
                ["vipsheader", "-f", "width", str(input_path)],
                self.settings.image_timeout_seconds,
                input_path.parent,
                env,
            ).stdout.strip()
            height = run_command(
                ["vipsheader", "-f", "height", str(input_path)],
                self.settings.image_timeout_seconds,
                input_path.parent,
                env,
            ).stdout.strip()
            try:
                dimensions = int(width), int(height)
            except ValueError as exc:
                raise ConverterError("invalid_file", "Image dimensions could not be read.", 422) from exc

        width_value, height_value = dimensions
        if width_value <= 0 or height_value <= 0:
            raise ConverterError("invalid_file", "Image dimensions are invalid.", 422)
        if width_value * height_value > self.settings.max_image_pixels:
            raise ConverterError(
                "invalid_file",
                "The decoded image dimensions exceed the configured pixel limit.",
                413,
            )
        return {"width": width_value, "height": height_value, "pixels": width_value * height_value}

    def _vips_convert(self, input_path: Path, output_path: Path, output_format: str) -> None:
        env = minimal_environment(input_path.parent)
        oriented = input_path.parent / "oriented.v"
        run_command(
            ["vips", "autorot", str(input_path), str(oriented)],
            self.settings.image_timeout_seconds,
            input_path.parent,
            env,
        )
        options = {
            "jpg": "[Q=90,strip,optimize-coding]",
            "webp": "[Q=88,strip,effort=4]",
            "avif": "[Q=55,strip,effort=5]",
            "png": "[strip,compression=8]",
            "tiff": "[strip,compression=lzw]",
        }[output_format]
        destination = f"{output_path}{options}"
        if output_format == "jpg" and self._vips_has_alpha(oriented, input_path.parent, env):
            run_command(
                ["vips", "flatten", str(oriented), destination, "--background", "255"],
                self.settings.image_timeout_seconds,
                input_path.parent,
                env,
            )
        else:
            run_command(
                ["vips", "copy", str(oriented), destination],
                self.settings.image_timeout_seconds,
                input_path.parent,
                env,
            )

    def _vips_has_alpha(self, path: Path, workspace: Path, env: dict[str, str]) -> bool:
        bands = run_command(
            ["vipsheader", "-f", "bands", str(path)],
            self.settings.image_timeout_seconds,
            workspace,
            env,
        ).stdout.strip()
        interpretation = run_command(
            ["vipsheader", "-f", "interpretation", str(path)],
            self.settings.image_timeout_seconds,
            workspace,
            env,
        ).stdout.casefold()
        try:
            band_count = int(bands)
        except ValueError as exc:
            raise ConverterError("invalid_file", "Image channel information could not be read.", 422) from exc

        monochrome = any(name in interpretation for name in ("b-w", "b_w", "grey16"))
        base_bands = 4 if "cmyk" in interpretation else 1 if monochrome else 3
        return band_count == base_bands + 1

    def _imagemagick_fallback(self, input_path: Path, output_path: Path, output_format: str) -> None:
        quality = {"jpg": "90", "webp": "88", "avif": "55"}.get(output_format)
        args = ["magick", str(input_path), "-auto-orient", "-strip"]
        if output_format == "jpg":
            args.extend(["-background", "white", "-alpha", "remove", "-alpha", "off"])
        if quality:
            args.extend(["-quality", quality])
        args.append(str(output_path))
        run_command(
            args,
            self.settings.image_timeout_seconds,
            input_path.parent,
            minimal_environment(input_path.parent),
        )

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        input_format: str,
        output_format: str,
        workspace: Path,
    ) -> ConversionResult:
        self.inspect(input_path)
        try:
            self._vips_convert(input_path, output_path, output_format)
            return ConversionResult(output_path, "libvips")
        except ConversionFailed:
            output_path.unlink(missing_ok=True)
            self._imagemagick_fallback(input_path, output_path, output_format)
            return ConversionResult(output_path, "imagemagick")
