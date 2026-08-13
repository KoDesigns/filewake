from __future__ import annotations

from backend.security.mime_detection import font_desktop_format


def test_woff2_true_type_flavor(tmp_path):
    path = tmp_path / "font.woff2"
    path.write_bytes(b"wOF2\x00\x01\x00\x00")
    assert font_desktop_format(path) == "ttf"


def test_woff_cff_flavor(tmp_path):
    path = tmp_path / "font.woff"
    path.write_bytes(b"wOFFOTTO")
    assert font_desktop_format(path) == "otf"
