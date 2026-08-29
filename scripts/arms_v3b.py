"""Protocol v3-B deterministic arm renderers: E1, E2 and E3.

Pure, offline and total. These render the exact model-facing content each architecture
would send. They perform no inference, attach no credentials and open no socket; freezing
them here is what makes "no prompt tuning after seeing outputs" checkable.

Reasoning-step parity (Amendment v3.2): at depth N every arm performs N reasoning calls
with the same instruction semantics and the same underlying task facts. Only the evidence
channel differs.

``E1``  every reasoning call carries the image
``E2``  one perception call carries the image; every reasoning call carries the symbolic
        handoff and NO image
``E3``  every reasoning call carries the oracle facts as text and NO image
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import economics_v3

E1 = economics_v3.E1_MULTIMODAL_RESIDENT
E2 = economics_v3.E2_ALPHACLAW
E3 = economics_v3.E3_TEXT_ORACLE

#: The single perception instruction E2 issues once at ingress.
E2_PERCEPTION_INSTRUCTION = (
    "Report the numbers shown in the image, in left-to-right order, as JSON matching "
    '{"observation": {"numbers_left_to_right": [...]}, "schema_version": 1}. '
    "Report only what is visible. Do not add, total or interpret the numbers."
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _item(item_id: str, document: dict[str, Any]) -> dict[str, Any]:
    for entry in document["items"]:
        if entry["item_id"] == item_id:
            return entry
    raise KeyError(item_id)


def perception_call(item_id: str, document: dict[str, Any]) -> dict[str, Any]:
    """E2's one multimodal call. Not a reasoning step."""
    entry = _item(item_id, document)
    return {
        "architecture": E2,
        "kind": "perception",
        "carries_image": True,
        "image_filename": entry["image_filename"],
        "image_sha256": entry["image_sha256"],
        "text": E2_PERCEPTION_INSTRUCTION,
        "text_sha256": _sha(E2_PERCEPTION_INSTRUCTION),
    }


def reasoning_calls(architecture: str, item_id: str, depth: int,
                    document: dict[str, Any]) -> list[dict[str, Any]]:
    """The N reasoning calls for one episode. Identical instruction across arms."""
    if architecture not in economics_v3.ARCHITECTURES:
        raise ValueError(f"unknown architecture {architecture!r}")
    entry = _item(item_id, document)
    episode = next(e for e in entry["episodes"] if e["depth"] == depth)

    calls = []
    for index, instruction in enumerate(episode["step_prompts"], start=1):
        call: dict[str, Any] = {
            "architecture": architecture,
            "kind": "reasoning",
            "step": index,
            "instruction": instruction,
            "instruction_sha256": _sha(instruction),
        }
        if architecture == E1:
            call.update(carries_image=True,
                        image_filename=entry["image_filename"],
                        image_sha256=entry["image_sha256"], evidence_text=None)
        elif architecture == E2:
            evidence = json.dumps(entry["symbolic_handoff"],
                                  ensure_ascii=False, sort_keys=True)
            call.update(carries_image=False, image_filename=None,
                        evidence_text=evidence, evidence_sha256=_sha(evidence))
        else:
            evidence = entry["oracle_facts"]
            call.update(carries_image=False, image_filename=None,
                        evidence_text=evidence, evidence_sha256=_sha(evidence))
        calls.append(call)
    return calls


def episode(architecture: str, item_id: str, depth: int,
            document: dict[str, Any]) -> dict[str, Any]:
    """One complete episode: its calls, its expected answer and its call counts."""
    entry = _item(item_id, document)
    expected = next(e for e in entry["episodes"]
                    if e["depth"] == depth)["expected_answer"]
    calls = reasoning_calls(architecture, item_id, depth, document)
    perception = [perception_call(item_id, document)] if architecture == E2 else []
    multimodal = sum(1 for c in perception + calls if c["carries_image"])
    text = sum(1 for c in perception + calls if not c["carries_image"])
    return {
        "architecture": architecture,
        "item_id": item_id,
        "depth": depth,
        "reasoning_steps": len(calls),
        "perception_calls": len(perception),
        "calls": perception + calls,
        "multimodal_calls": multimodal,
        "text_calls": text,
        "total_provider_calls": len(perception) + len(calls),
        "expected_answer": expected,
        "output_contract": entry["output_contract"],
    }


def call_matrix(document: dict[str, Any]) -> dict[str, Any]:
    """Regenerate the whole planned V3-B matrix from the frozen fixtures."""
    episodes, multimodal, text = [], 0, 0
    for entry in document["items"]:
        for depth in document["depths"]:
            for architecture in economics_v3.ARCHITECTURES:
                built = episode(architecture, entry["item_id"], depth, document)
                episodes.append({k: built[k] for k in
                                 ("architecture", "item_id", "depth", "reasoning_steps",
                                  "perception_calls", "multimodal_calls", "text_calls",
                                  "total_provider_calls", "expected_answer")})
                multimodal += built["multimodal_calls"]
                text += built["text_calls"]
    return {
        "episodes": episodes,
        "items": len(document["items"]),
        "repeats": document["repeats"],
        "depths": list(document["depths"]),
        "multimodal_calls": multimodal,
        "text_calls": text,
        "total_calls": multimodal + text,
    }


def leakage_report(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Every episode's model-facing text, checked against its own answer and chain.

    Within-episode rule: an episode's expected final answer must never appear in any of
    that episode's prompts, and no prompt may carry more than the single running total
    handed in as state.
    """
    import re

    rows = []
    for entry in document["items"]:
        for depth in document["depths"]:
            expected = next(e for e in entry["episodes"]
                            if e["depth"] == depth)["expected_answer"]
            chain = next(e for e in entry["episodes"]
                         if e["depth"] == depth)["chain"]
            for architecture in economics_v3.ARCHITECTURES:
                built = episode(architecture, entry["item_id"], depth, document)
                blob = " ".join(
                    part for call in built["calls"]
                    for part in (call.get("instruction") or "",
                                 call.get("text") or "",
                                 call.get("evidence_text") or ""))
                anchored = rf"(?<![0-9]){re.escape(expected)}(?![0-9])"
                totals_present = [
                    step["running_total"] for step in chain
                    if re.search(rf"(?<![0-9]){step['running_total']}(?![0-9])", blob)]
                present = re.search(anchored, blob) is not None
                # At depth 1 the answer IS the first displayed integer, so any arm whose
                # evidence is text necessarily contains it. That is a property of the
                # task at depth 1, not an injected leak, and it is recorded rather than
                # engineered away: the frozen protocol fixes the depths.
                inherent = (depth == 1 and architecture != E1)
                rows.append({
                    "architecture": architecture,
                    "item_id": entry["item_id"],
                    "depth": depth,
                    "expected_answer": expected,
                    "answer_present_in_prompts": present,
                    "inherent_at_depth_1": inherent,
                    "answer_leaked": present and not inherent,
                    "running_totals_visible": totals_present,
                    "full_chain_leaked": len(totals_present) >= max(2, len(chain)),
                })
    return rows
