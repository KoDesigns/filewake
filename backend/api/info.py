from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter

from backend.config import get_settings
from backend.conversion.registry import registry


router = APIRouter()


def package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


@router.get("/info")
async def info() -> dict:
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "stateless": True,
        "persistent_storage": False,
        "categories": list(registry.categories()),
        "framework_versions": {
            "fastapi": package_version("fastapi"),
            "starlette": package_version("starlette"),
            "fonttools": package_version("fonttools"),
        },
        "limits": {
            "max_file_size_mb": settings.max_file_size_mb,
            "max_batch_files": settings.max_batch_files,
            "max_batch_size_mb": settings.max_batch_size_mb,
            "max_parallel_conversions": settings.max_parallel_conversions,
            "max_image_pixels": settings.max_image_pixels,
            "max_output_size_mb": settings.max_output_size_mb,
        },
    }
