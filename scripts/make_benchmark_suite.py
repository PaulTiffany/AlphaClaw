"""Generate the controlled six-family benchmark suite and its ground truth.

Six matched families. Each item yields three conditions from one underlying task:
a text control, an image-only condition, and an image+text condition sharing the
exact same image bytes.

Every exact-answer rule states its formatting contract explicitly. An under-specified
contract previously produced ``K7 3`` against an expected ``K73``; that was a stimulus
defect, not a model failure, and the explicit contracts here are the fix.

Stdlib only, and deterministic: zlib level 0 keeps the bytes identical on every
machine, so the digests recorded in ground truth are stable.

Usage:
    python scripts/make_benchmark_suite.py --output-dir benchmark/stimuli \\
                                           --ground-truth benchmark/items.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_benchmark_stimuli import (
    BLACK,
    BLUE,
    GLYPH_SCALE,
    GLYPHS,
    WHITE,
    _chunk,
    _draw_glyph,
    _fill_rect,
)

RED = (255, 0, 0)
WIDTH = 152
HEIGHT = 56
SQUARE = 12
SQUARE_Y = 22
TEXT_Y = 18
GLYPH_ADVANCE = 5 * GLYPH_SCALE + GLYPH_SCALE
COLOURS = {"blue": BLUE, "red": RED}

_FORMAT = "Reply with no spaces and no other text."

SUITE = [
    {
        "item_id": "ocr_count",
        "family": "OCR + count",
        "probe": "perception",
        "squares": [("blue", x) for x in (8, 26, 44, 62, 80)],
        "texts": [("M4", 100)],
        "rule": (
            "Reply with the token shown, then the number of squares. Use uppercase "
            f"for the token and digits only for the count. {_FORMAT}"
        ),
        "control_facts": "The token M4 is shown. There are 5 blue squares.",
        "expected_answer": "M45",
        "facts": [
            {"type": "token", "value": "M4"},
            {"type": "shape_presence", "colour": "blue", "shape": "square"},
            {"type": "shape_count", "colour": "blue", "shape": "square", "value": 5},
        ],
    },
    {
        "item_id": "colour_count",
        "family": "colour + count",
        "probe": "perception",
        "squares": [("red", 8), ("red", 26), ("red", 44), ("blue", 70), ("blue", 88)],
        "texts": [],
        "rule": (
            "Reply with the number of red squares then the number of blue squares. "
            f"Use digits only. {_FORMAT}"
        ),
        "control_facts": "There are 3 red squares and 2 blue squares.",
        "expected_answer": "32",
        "facts": [
            {"type": "shape_presence", "colour": "red", "shape": "square"},
            {"type": "shape_count", "colour": "red", "shape": "square", "value": 3},
            {"type": "shape_presence", "colour": "blue", "shape": "square"},
            {"type": "shape_count", "colour": "blue", "shape": "square", "value": 2},
        ],
    },
    {
        "item_id": "spatial_relation",
        "family": "spatial relation",
        "probe": "perception",
        "squares": [("red", 10), ("blue", 120)],
        "texts": [],
        "rule": (
            f"Reply with the colour word of the leftmost square. Use uppercase. {_FORMAT}"
        ),
        "control_facts": "A red square is on the left and a blue square is on the right.",
        "expected_answer": "RED",
        "facts": [
            {"type": "shape_presence", "colour": "red", "shape": "square"},
            {"type": "shape_presence", "colour": "blue", "shape": "square"},
            {
                "type": "relation",
                "subject_colour": "red",
                "subject_shape": "square",
                "predicate": "left_of",
                "object_colour": "blue",
                "object_shape": "square",
            },
        ],
    },
    {
        "item_id": "number_arithmetic",
        "family": "visible-number arithmetic",
        # Deliberately a resident-reasoning probe rather than pure perception. The
        # matched text control separates arithmetic failure from sensory failure.
        "probe": "resident_reasoning",
        "squares": [],
        "texts": [("12", 20), ("7", 100)],
        "rule": (
            f"Add the two numbers shown and reply with their sum. Use digits only. {_FORMAT}"
        ),
        "control_facts": "The numbers 12 and 7 are shown.",
        "expected_answer": "19",
        "facts": [
            {"type": "number", "value": 12},
            {"type": "number", "value": 7},
        ],
    },
    {
        "item_id": "distractor_selection",
        "family": "distractor / visual selection",
        "probe": "perception",
        "squares": [("blue", 8), ("blue", 26), ("blue", 44), ("blue", 62), ("red", 90)],
        "texts": [],
        "rule": (
            "Reply with the colour word of the square that appears exactly once. "
            f"Use uppercase. {_FORMAT}"
        ),
        "control_facts": "There are 4 blue squares and 1 red square.",
        "expected_answer": "RED",
        "facts": [
            {"type": "shape_presence", "colour": "blue", "shape": "square"},
            {"type": "shape_count", "colour": "blue", "shape": "square", "value": 4},
            {"type": "shape_presence", "colour": "red", "shape": "square"},
            {"type": "shape_count", "colour": "red", "shape": "square", "value": 1},
        ],
    },
    {
        "item_id": "multi_fact_composition",
        "family": "multi-fact relation + composition",
        "probe": "perception",
        "squares": [("blue", 8), ("blue", 26), ("blue", 44), ("red", 70), ("red", 88)],
        "texts": [("Q9", 112)],
        "rule": (
            "Reply with the token, then the number of blue squares, then the number of "
            "red squares. Use uppercase for the token and digits only for the counts. "
            f"{_FORMAT}"
        ),
        "control_facts": "The token Q9 is shown. There are 3 blue squares and 2 red squares.",
        "expected_answer": "Q932",
        "facts": [
            {"type": "token", "value": "Q9"},
            {"type": "shape_presence", "colour": "blue", "shape": "square"},
            {"type": "shape_count", "colour": "blue", "shape": "square", "value": 3},
            {"type": "shape_presence", "colour": "red", "shape": "square"},
            {"type": "shape_count", "colour": "red", "shape": "square", "value": 2},
        ],
    },
]


def _png(raw_scanlines: bytes, width: int, height: int) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw_scanlines, 0))
        + _chunk(b"IEND", b"")
    )


def render_item(spec: dict) -> bytes:
    px = [[WHITE for _ in range(WIDTH)] for _ in range(HEIGHT)]
    for colour, left in spec["squares"]:
        _fill_rect(px, left, SQUARE_Y, SQUARE, SQUARE, COLOURS[colour])
    for token, left in spec["texts"]:
        for offset, char in enumerate(token):
            _draw_glyph(px, GLYPHS[char], left + offset * GLYPH_ADVANCE, TEXT_Y, GLYPH_SCALE)
    assert BLACK  # glyphs are drawn in black by _draw_glyph

    raw = bytearray()
    for row in px:
        raw.append(0)
        for r, g, b in row:
            raw += bytes((r, g, b))
    return _png(bytes(raw), WIDTH, HEIGHT)


def _sha(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def build_suite(output_dir: Path | None = None) -> dict:
    """Render every item and return the ground-truth document.

    When ``output_dir`` is None the PNGs are rendered but not written, so tests can
    verify digests without touching the filesystem.
    """
    items = []
    for spec in SUITE:
        data = render_item(spec)
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / f"{spec['item_id']}.png").write_bytes(data)
        control = f"{spec['control_facts']} {spec['rule']}"
        items.append(
            {
                "item_id": spec["item_id"],
                "family": spec["family"],
                "probe": spec["probe"],
                "image_filename": f"{spec['item_id']}.png",
                "image_sha256": _sha(data),
                "image_bytes": len(data),
                "rule_text": spec["rule"],
                "rule_sha256": _sha(spec["rule"]),
                "text_control_input": control,
                "text_control_sha256": _sha(control),
                "expected_answer": spec["expected_answer"],
                "facts": spec["facts"],
                "atomic_fact_count": len(spec["facts"]),
            }
        )
    return {
        "schema_version": 1,
        "generator": "scripts/make_benchmark_suite.py",
        "canvas": {"width": WIDTH, "height": HEIGHT},
        "reasoning_condition": {
            "provider": "asicloud",
            "model": "minimax/minimax-m3",
            "max_new_input_loops": 1,
            "max_wake_loops": 0,
            "max_history": 0,
            "note": (
                "Fixed sponsored resident reasoning condition for this tranche. Held "
                "constant across all items; not a benchmark-tuning target and not "
                "compared against other resident models here."
            ),
        },
        "items": items,
        "total_atomic_facts": sum(i["atomic_fact_count"] for i in items),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    args = parser.parse_args()

    doc = build_suite(args.output_dir)
    args.ground_truth.parent.mkdir(parents=True, exist_ok=True)
    args.ground_truth.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for item in doc["items"]:
        print(f"{item['item_id']:<24} {item['image_sha256']}  {item['image_bytes']} bytes")
    print(f"total atomic facts: {doc['total_atomic_facts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
