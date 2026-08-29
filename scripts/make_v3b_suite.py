"""Protocol v3-B stimulus family: ``chained_accumulation``. Deterministic, stdlib only.

Implements the family Protocol v3 preregistered. It is a NEW module: no v2 stimulus
generator and no frozen v2 item is touched, and the frozen drawing primitives are
imported rather than reimplemented so the bytes stay reproducible.

One image shows eight integers in a fixed left-to-right order. An episode at reasoning
depth N consists of N sequential reasoning calls; call *i* adds the *i*-th integer to the
running total carried in from call *i-1* and returns the new running total. The episode's
expected answer is the running total after step N.

Depth therefore varies the number of reasoning CALLS while the perceived evidence stays
constant, which is exactly what lets one perception serve every depth in E2.

The digit glyphs available in the frozen renderer are 1, 2, 4, 5, 7 and 9, so every
displayed integer is composed only of those digits. Running totals are never displayed;
they are produced by the model as text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_benchmark_stimuli import (
    GLYPH_SCALE,
    GLYPHS,
    WHITE,
    _chunk,
    _draw_glyph,
)

FAMILY = "chained_accumulation"

WIDTH = 420
HEIGHT = 40
TEXT_Y = 12
GLYPH_ADVANCE = 5 * GLYPH_SCALE + GLYPH_SCALE
SLOT = 50
LEFT_MARGIN = 8

#: Digits the frozen glyph table can render.
RENDERABLE_DIGITS = frozenset("124579")

#: Preregistered depths. Exactly these, no more.
DEPTHS = (1, 2, 4, 8)

#: The frozen population: exactly two items, one repeat, as Protocol v3 specifies.
#: The integers are fixed constants -- they are the generator's input parameters -- and
#: are chosen so that every scored running total is distinct from every displayed
#: integer, except at depth 1 where the answer IS the first integer by construction of
#: the task.
ITEMS: tuple[dict[str, Any], ...] = (
    {"item_id": "chain_a", "integers": (7, 12, 5, 9, 14, 2, 11, 4)},
    {"item_id": "chain_b", "integers": (9, 12, 4, 15, 7, 22, 5, 11)},
)

OUTPUT_CONTRACT = "Use digits only. Reply with no spaces and no other text."

#: One reasoning step. ``previous`` is the state carried in, never the step's answer.
STEP_INSTRUCTION = (
    "The numbers are added one at a time, from left to right. "
    "The running total after step {previous_step} is {previous_total}. "
    "Add the number at position {step} and reply with the new running total. "
    + OUTPUT_CONTRACT
)


class SuiteError(ValueError):
    """The frozen population violates one of its own constraints."""


def _sha(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _png(raw_scanlines: bytes, width: int, height: int) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw_scanlines, 0))
        + _chunk(b"IEND", b"")
    )


def render_item(spec: dict[str, Any]) -> bytes:
    """Render the eight integers left to right. Deterministic: zlib level 0."""
    pixels = [[WHITE for _ in range(WIDTH)] for _ in range(HEIGHT)]
    for index, value in enumerate(spec["integers"]):
        text = str(value)
        if not set(text) <= RENDERABLE_DIGITS:
            raise SuiteError(
                f"{spec['item_id']}: {value} uses a digit the frozen glyph table cannot "
                f"render (available: {''.join(sorted(RENDERABLE_DIGITS))})")
        left = LEFT_MARGIN + index * SLOT
        for offset, char in enumerate(text):
            _draw_glyph(pixels, GLYPHS[char], left + offset * GLYPH_ADVANCE,
                        TEXT_Y, GLYPH_SCALE)

    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for red, green, blue in row:
            raw += bytes((red, green, blue))
    return _png(bytes(raw), WIDTH, HEIGHT)


def reasoning_chain(integers: tuple[int, ...], depth: int) -> list[dict[str, int]]:
    """Full step-by-step chain for one episode. Ground truth only -- never prompted."""
    chain, total = [], 0
    for step in range(1, depth + 1):
        addend = integers[step - 1]
        total += addend
        chain.append({"step": step, "addend": addend, "running_total": total})
    return chain


def expected_answer(integers: tuple[int, ...], depth: int) -> str:
    return str(sum(integers[:depth]))


def step_prompt(integers: tuple[int, ...], step: int) -> str:
    """The instruction for one reasoning call. Carries state in, never the answer."""
    previous_total = sum(integers[: step - 1])
    return STEP_INSTRUCTION.format(previous_step=step - 1, previous_total=previous_total,
                                   step=step)


def oracle_facts(integers: tuple[int, ...]) -> str:
    """E3's text-oracle evidence: exactly the visual facts, no totals, no chain."""
    listed = ", ".join(str(value) for value in integers)
    return f"The numbers shown, in left-to-right order, are: {listed}."


def symbolic_handoff(integers: tuple[int, ...]) -> dict[str, Any]:
    """The symbolic form E2 reuses across every later text-only reasoning call."""
    return {"observation": {"numbers_left_to_right": list(integers)},
            "schema_version": 1}


def _validate(item: dict[str, Any]) -> None:
    integers = item["integers"]
    if len(integers) != 8:
        raise SuiteError(f"{item['item_id']}: expected eight integers")
    displayed = set(integers)
    scored = {sum(integers[:depth]) for depth in DEPTHS if depth > 1}
    overlap = scored & displayed
    if overlap:
        raise SuiteError(
            f"{item['item_id']}: scored running totals {sorted(overlap)} collide with a "
            "displayed integer, which would make a wrong answer indistinguishable")
    if len(scored) != len([d for d in DEPTHS if d > 1]):
        raise SuiteError(f"{item['item_id']}: scored running totals are not distinct")


def build_suite(output_dir: Path | None = None) -> dict[str, Any]:
    """Render every item and return the ground-truth document.

    With ``output_dir`` None the PNGs are rendered but not written, so a test can verify
    digests without touching the filesystem.
    """
    items = []
    for spec in ITEMS:
        _validate(spec)
        integers = spec["integers"]
        image = render_item(spec)
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / f"{spec['item_id']}.png").write_bytes(image)

        episodes = []
        for depth in DEPTHS:
            chain = reasoning_chain(integers, depth)
            prompts = [step_prompt(integers, step) for step in range(1, depth + 1)]
            episodes.append({
                "depth": depth,
                "reasoning_steps": depth,
                "chain": chain,
                "expected_answer": expected_answer(integers, depth),
                "step_prompts": prompts,
                "step_prompt_sha256": [_sha(p) for p in prompts],
            })

        items.append({
            "item_id": spec["item_id"],
            "family": FAMILY,
            "integers": list(integers),
            "initial_state": 0,
            "image_filename": f"{spec['item_id']}.png",
            "image_sha256": _sha(image),
            "output_contract": OUTPUT_CONTRACT,
            "oracle_facts": oracle_facts(integers),
            "oracle_facts_sha256": _sha(oracle_facts(integers)),
            "symbolic_handoff": symbolic_handoff(integers),
            "episodes": episodes,
        })

    document = {
        "schema_version": 1,
        "protocol_version": "v3",
        "section": "V3-B",
        "family": FAMILY,
        "depths": list(DEPTHS),
        "repeats": 1,
        "generator": "scripts/make_v3b_suite.py",
        "deterministic": True,
        "renderable_digits": "".join(sorted(RENDERABLE_DIGITS)),
        "step_instruction_template": STEP_INSTRUCTION,
        "depth_1_property": (
            "At depth 1 the expected answer equals the first displayed integer, because "
            "the task is to add that integer to an initial state of 0. Any arm whose "
            "evidence is text (E2, E3) therefore contains the answer verbatim, while E1 "
            "must still read it from the image. Depth 1 is consequently a degenerate "
            "ACCURACY comparison and is retained only as the no-amortisation economic "
            "baseline, where expected multimodal avoidance is 0%. This is a property of "
            "the preregistered task at depth 1, recorded rather than engineered away; "
            "the frozen protocol fixes the depths as 1, 2, 4 and 8."),
        "items": items,
    }
    document["ground_truth_sha256"] = _sha(
        json.dumps(document, ensure_ascii=False, sort_keys=True))
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    args = parser.parse_args()

    document = build_suite(args.output_dir)
    args.ground_truth.parent.mkdir(parents=True, exist_ok=True)
    # write_bytes does no newline translation, so the committed blob stays LF on every
    # platform and matches the digest the tests pin.
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    args.ground_truth.write_bytes(text.encode("utf-8"))
    for item in document["items"]:
        print(f"{item['item_id']}: {item['image_sha256']} {item['integers']}")
    print(f"ground truth: {document['ground_truth_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
