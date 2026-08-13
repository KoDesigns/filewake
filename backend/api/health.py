from __future__ import annotations

from importlib.util import find_spec

from fastapi import APIRouter

from backend.runtime.subprocess import converter_executable


router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "engines": {
            "ffmpeg": converter_executable("ffmpeg") is not None,
            "ffprobe": converter_executable("ffprobe") is not None,
            "libvips": converter_executable("vips") is not None,
            "imagemagick": converter_executable("magick") is not None,
            "libreoffice": converter_executable("libreoffice") is not None,
            "pandoc": converter_executable("pandoc") is not None,
            "fonttools": find_spec("fontTools") is not None,
        },
    }
