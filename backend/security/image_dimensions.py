from __future__ import annotations

import struct
from pathlib import Path


_MAX_HEADER_BYTES = 8 * 1024 * 1024
_JPEG_SOF_MARKERS = {
    0xC0,
    0xC1,
    0xC2,
    0xC3,
    0xC5,
    0xC6,
    0xC7,
    0xC9,
    0xCA,
    0xCB,
    0xCD,
    0xCE,
    0xCF,
}


def _png_dimensions(header: bytes) -> tuple[int, int] | None:
    if len(header) < 24 or not header.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    if header[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", header[16:24])


def _webp_dimensions(header: bytes) -> tuple[int, int] | None:
    if len(header) < 25 or header[:4] != b"RIFF" or header[8:12] != b"WEBP":
        return None

    chunk = header[12:16]
    if chunk == b"VP8X" and len(header) >= 30:
        width = 1 + int.from_bytes(header[24:27], "little")
        height = 1 + int.from_bytes(header[27:30], "little")
        return width, height

    if chunk == b"VP8 " and len(header) >= 30 and header[23:26] == b"\x9d\x01\x2a":
        width = int.from_bytes(header[26:28], "little") & 0x3FFF
        height = int.from_bytes(header[28:30], "little") & 0x3FFF
        return width, height

    if chunk == b"VP8L" and len(header) >= 25 and header[20] == 0x2F:
        bits = int.from_bytes(header[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    return None


def _jpeg_dimensions(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as source:
        if source.read(2) != b"\xff\xd8":
            return None

        while source.tell() < _MAX_HEADER_BYTES:
            byte = source.read(1)
            while byte and byte != b"\xff":
                byte = source.read(1)
            if not byte:
                return None

            marker = source.read(1)
            while marker == b"\xff":
                marker = source.read(1)
            if not marker:
                return None

            marker_value = marker[0]
            if marker_value in {0x01, 0xD8} or 0xD0 <= marker_value <= 0xD7:
                continue
            if marker_value in {0xD9, 0xDA}:
                return None

            raw_length = source.read(2)
            if len(raw_length) != 2:
                return None
            segment_length = int.from_bytes(raw_length, "big")
            if segment_length < 2:
                return None

            if marker_value in _JPEG_SOF_MARKERS:
                dimensions = source.read(5)
                if len(dimensions) != 5:
                    return None
                height = int.from_bytes(dimensions[1:3], "big")
                width = int.from_bytes(dimensions[3:5], "big")
                return width, height

            source.seek(segment_length - 2, 1)
    return None


def _tiff_dimensions(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as source:
        header = source.read(8)
        if len(header) != 8 or header[:2] not in {b"II", b"MM"}:
            return None
        byte_order = "little" if header[:2] == b"II" else "big"
        if int.from_bytes(header[2:4], byte_order) != 42:
            return None
        ifd_offset = int.from_bytes(header[4:8], byte_order)
        if ifd_offset < 8 or ifd_offset > _MAX_HEADER_BYTES:
            return None
        source.seek(ifd_offset)
        raw_count = source.read(2)
        if len(raw_count) != 2:
            return None
        entry_count = min(int.from_bytes(raw_count, byte_order), 4096)
        values: dict[int, int] = {}
        for _ in range(entry_count):
            entry = source.read(12)
            if len(entry) != 12:
                return None
            tag = int.from_bytes(entry[:2], byte_order)
            value_type = int.from_bytes(entry[2:4], byte_order)
            count = int.from_bytes(entry[4:8], byte_order)
            if tag not in {256, 257} or count != 1 or value_type not in {3, 4}:
                continue
            width = 2 if value_type == 3 else 4
            values[tag] = int.from_bytes(entry[8 : 8 + width], byte_order)
        if 256 in values and 257 in values:
            return values[256], values[257]
    return None


def _isobmff_dimensions(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as source:
        data = source.read(_MAX_HEADER_BYTES)
    offset = 0
    while True:
        marker = data.find(b"ispe", offset)
        if marker < 0:
            return None
        if marker >= 4 and marker + 16 <= len(data):
            box_size = int.from_bytes(data[marker - 4 : marker], "big")
            if box_size >= 20:
                width = int.from_bytes(data[marker + 8 : marker + 12], "big")
                height = int.from_bytes(data[marker + 12 : marker + 16], "big")
                if width and height:
                    return width, height
        offset = marker + 4


def read_image_dimensions(path: Path) -> tuple[int, int] | None:
    """Read dimensions from bounded image headers without decoding pixel data."""

    with path.open("rb") as source:
        header = source.read(32)

    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return _png_dimensions(header)
    if header.startswith(b"\xff\xd8"):
        return _jpeg_dimensions(path)
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return _webp_dimensions(header)
    if header[:4] in {b"II*\x00", b"MM\x00*"}:
        return _tiff_dimensions(path)
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return _isobmff_dimensions(path)
    return None
