from __future__ import annotations

import re
import unicodedata
from pathlib import Path


_UNSAFE = re.compile(r"[^A-Za-z0-9._ -]+")


def safe_download_name(original_name: str | None, output_format: str) -> str:
    raw_name = Path((original_name or "converted").replace("\\", "/")).name
    stem = Path(raw_name).stem
    stem = unicodedata.normalize("NFKC", stem)
    stem = _UNSAFE.sub("_", stem).strip(" ._")[:120] or "converted"
    extension = re.sub(r"[^a-z0-9]", "", output_format.lower())
    return f"{stem}.{extension}"


def content_disposition(filename: str) -> str:
    # safe_download_name deliberately emits an ASCII-only name.
    escaped = filename.replace('"', "")
    return f'attachment; filename="{escaped}"'
