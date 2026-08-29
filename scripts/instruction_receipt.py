"""Protocol v3 instruction-position receipt.

Records where Alpha's instruction actually sits inside the resident-facing prompt,
relative to Omega's own context, the human task and the symbolic evidence.

Observable positional facts ONLY. There is deliberately no "salience score": nothing
here models attention, importance or psychology. It answers one narrow question --

    a preserved prepend can still be operationally distant from the answer-required
    task; how distant, in characters, and in what order?

Token counts are reported only where a provider receipt supplies them for the whole
request. Per-segment token counts are not mechanically available and are recorded as
``None`` rather than estimated.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

#: The components located within a resident-facing prompt, in no privileged order.
#: ``omega_context`` is stock OmegaClaw's own prompt / skill-action instructions. It is
#: part of the failure surface under test and must be located, not assumed away.
COMPONENTS = ("alpha_instruction", "human_task", "symbolic_evidence", "omega_context")


def _escaped(text: str) -> str:
    """The form a string takes when embedded inside a JSON string value."""
    return json.dumps(text, ensure_ascii=False)[1:-1]


def _locate(haystack: str, needle: str | None) -> dict[str, Any]:
    """Locate a component, trying the literal form then the JSON-escaped form.

    A payload embedded in the Alpha envelope appears escaped, so a literal-only search
    would report a present component as missing. Which form matched is recorded rather
    than hidden.
    """
    missing = {"found": False, "start": None, "end": None, "matched_form": None,
               "chars_before": None, "chars_after": None, "chars": None}
    if not needle:
        return missing

    for form, candidate in (("literal", needle), ("json_escaped", _escaped(needle))):
        start = haystack.find(candidate)
        if start >= 0:
            end = start + len(candidate)
            return {
                "found": True,
                "start": start,
                "end": end,
                "matched_form": form,
                "chars": len(candidate),
                "chars_before": start,
                "chars_after": len(haystack) - end,
            }
    return {**missing, "chars": len(needle)}


def positions(
    prompt: str,
    *,
    alpha_instruction: str | None = None,
    human_task: str | None = None,
    symbolic_evidence: str | None = None,
    omega_context: str | None = None,
    request_tokens: int | None = None,
) -> dict[str, Any]:
    """Locate each component inside the exact resident-facing prompt text.

    ``prompt`` is the literal text sent to the resident. Every offset is a character
    index into it, so the receipt is reproducible from the prompt alone.
    """
    located = {
        "alpha_instruction": _locate(prompt, alpha_instruction),
        "human_task": _locate(prompt, human_task),
        "symbolic_evidence": _locate(prompt, symbolic_evidence),
        "omega_context": _locate(prompt, omega_context),
    }

    found = [(name, block["start"]) for name, block in located.items() if block["found"]]
    found.sort(key=lambda pair: pair[1])
    order = [name for name, _ in found]

    receipt: dict[str, Any] = {
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_chars": len(prompt),
        "components": located,
        "order": order,
        "order_rank": {name: rank for rank, name in enumerate(order)},
        "all_components_found": all(block["found"] for block in located.values()),
        # whole-request tokens only; per-segment tokens are not mechanically available
        "request_tokens": request_tokens,
        "per_segment_tokens_available": False,
        "salience_score_reported": False,
    }

    alpha = located["alpha_instruction"]
    task = located["human_task"]
    if alpha["found"] and task["found"]:
        receipt["chars_between_alpha_instruction_and_human_task"] = (
            task["start"] - alpha["end"] if task["start"] >= alpha["end"]
            else alpha["start"] - task["end"])
        receipt["alpha_instruction_precedes_human_task"] = alpha["start"] < task["start"]
    else:
        receipt["chars_between_alpha_instruction_and_human_task"] = None
        receipt["alpha_instruction_precedes_human_task"] = None

    evidence = located["symbolic_evidence"]
    if alpha["found"] and evidence["found"]:
        receipt["alpha_instruction_precedes_symbolic_evidence"] = (
            alpha["start"] < evidence["start"])
    else:
        receipt["alpha_instruction_precedes_symbolic_evidence"] = None

    omega = located["omega_context"]
    receipt["omega_context_located"] = omega["found"]
    if omega["found"] and task["found"]:
        receipt["omega_context_precedes_human_task"] = omega["start"] < task["start"]
    else:
        receipt["omega_context_precedes_human_task"] = None
    return receipt


def distance_summary(receipt: dict[str, Any]) -> dict[str, Any]:
    """The two figures V3-A actually reasons about, extracted without interpretation."""
    alpha = receipt["components"]["alpha_instruction"]
    task = receipt["components"]["human_task"]
    omega = receipt["components"]["omega_context"]
    return {
        "alpha_instruction_chars_before": alpha["chars_before"],
        "alpha_instruction_chars_after": alpha["chars_after"],
        "human_task_chars_before": task["chars_before"],
        "human_task_chars_after": task["chars_after"],
        "omega_context_chars_before": omega["chars_before"],
        "omega_context_chars_after": omega["chars_after"],
        "omega_context_located": omega["found"],
        "order": receipt["order"],
        "prompt_chars": receipt["prompt_chars"],
    }
