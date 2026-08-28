"""Generate the deterministic multimodal benchmark stimulus.

Stdlib only. The repository declares no runtime dependencies, and drawing three
squares and two glyphs does not justify adding an imaging library.

Determinism matters more than file size here: the PNG's SHA-256 is pinned in the
tests and recorded in benchmark receipts, so the same bytes must be produced on
every machine. zlib compression level 0 (stored blocks) is used deliberately --
higher levels can differ between zlib builds, which would change the digest.

Usage:
    python scripts/make_benchmark_stimuli.py --output stimulus.png
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import zlib
from pathlib import Path

WIDTH = 96
HEIGHT = 48

WHITE = (255, 255, 255)
BLUE = (0, 0, 255)
BLACK = (0, 0, 0)

SQUARE_SIZE = 10
SQUARE_TOP = 18
SQUARE_LEFT = (6, 20, 34)

GLYPH_SCALE = 3
GLYPH_TOP = 14
GLYPH_LEFT = (54, 72)

# 5x7 bitmap glyphs for the literal token drawn into the image.
GLYPHS = {
    "K": (
        "X...X",
        "X..X.",
        "X.X..",
        "XX...",
        "X.X..",
        "X..X.",
        "X...X",
    ),
    "7": (
        "XXXXX",
        "....X",
        "...X.",
        "..X..",
        ".X...",
        ".X...",
        ".X...",
    ),
}
TOKEN = "K7"


def _blank() -> list[list[tuple[int, int, int]]]:
    return [[WHITE for _ in range(WIDTH)] for _ in range(HEIGHT)]


def _fill_rect(px, left: int, top: int, width: int, height: int, colour) -> None:
    for y in range(top, top + height):
        for x in range(left, left + width):
            px[y][x] = colour


def _draw_glyph(px, glyph: tuple[str, ...], left: int, top: int, scale: int) -> None:
    for row, bits in enumerate(glyph):
        for col, bit in enumerate(bits):
            if bit != "X":
                continue
            _fill_rect(px, left + col * scale, top + row * scale, scale, scale, BLACK)


def render() -> bytes:
    """Three blue squares on white, plus the literal black token K7."""
    px = _blank()
    for left in SQUARE_LEFT:
        _fill_rect(px, left, SQUARE_TOP, SQUARE_SIZE, SQUARE_SIZE, BLUE)
    for char, left in zip(TOKEN, GLYPH_LEFT):
        _draw_glyph(px, GLYPHS[char], left, GLYPH_TOP, GLYPH_SCALE)

    raw = bytearray()
    for row in px:
        raw.append(0)  # PNG filter type 0 (None) for every scanline
        for r, g, b in row:
            raw += bytes((r, g, b))
    return _png(bytes(raw))


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def _png(raw_scanlines: bytes) -> bytes:
    ihdr = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw_scanlines, 0))
        + _chunk(b"IEND", b"")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    data = render()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"{args.output}  bytes={len(data)}  sha256={hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
