from __future__ import annotations

import sys
from pathlib import Path

from fontTools.ttLib import TTFont


def main() -> int:
    if len(sys.argv) != 4:
        return 2
    source, destination, target = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    if target not in {"ttf", "otf", "woff", "woff2"}:
        return 2
    font = TTFont(source, lazy=False, recalcBBoxes=False, recalcTimestamp=False)
    desktop_format = "otf" if font.sfntVersion == "OTTO" else "ttf"
    if target in {"ttf", "otf"} and target != desktop_format:
        return 3
    font.flavor = target if target in {"woff", "woff2"} else None
    font.save(destination, reorderTables=True)
    font.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
