from __future__ import annotations

import struct

from backend.security.image_dimensions import read_image_dimensions


def png_header(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x06\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )


def test_png_dimensions_do_not_require_vipsheader(tmp_path):
    path = tmp_path / "input.png"
    path.write_bytes(png_header(1440, 900))
    assert read_image_dimensions(path) == (1440, 900)


def test_png_inspection_does_not_require_vipsheader(client):
    response = client.post(
        "/api/inspect",
        files={"file": ("Designer (9).png", png_header(1200, 800), "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["detected_format"] == "png"
    assert response.json()["details"] == {"width": 1200, "height": 800, "pixels": 960000}


def test_png_pixel_bomb_is_rejected_without_vipsheader(client, workspace_root):
    response = client.post(
        "/api/inspect",
        files={"file": ("huge.png", png_header(20_000, 20_000), "image/png")},
    )
    assert response.status_code == 413
    assert response.json()["error"] == "invalid_file"
    assert not list(workspace_root.glob("job-*"))
