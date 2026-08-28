"""Protocol Amendment v2.2 -- composition replay for condition B2.

Protocol v2 preregistered B2 as an image+text condition with zero sensory calls, but
the replay tooling could only re-deliver a *raw* handoff. Raw replay drops the frozen
human instruction, and the live combined route (``route_image_with_text``) refuses a
non-image input and would demand a sensory call. B2 was therefore not executable as
written: exact-match grading was unsatisfiable because the resident was never told
what to answer.

This amendment makes the already-preregistered intervention executable and changes
nothing else. The intervention remains:

    same task text + alternate sensory evidence -> same MiniMax resident

Two independently frozen constituents
-------------------------------------
1. the exact human instruction from the existing image+text benchmark item;
2. the exact B1 ``repeat_index = 0`` sensory handoff, fixed by Amendment v2.1.

Clarification of the v2 byte-identity invariant
-----------------------------------------------
It is **wrong** to claim the whole B2 replay input equals the raw B1 handoff. For an
image+text replay the correct invariant is:

* sensory constituent  == the exact frozen B1 handoff;
* text constituent     == the exact frozen benchmark instruction;
* combined payload     == a deterministic composition of those two constituents;
* composed payload     == byte-identical to what the live image+text route would
  produce if handed that same handoff.

This is a clarification of the intervention boundary, not permission to alter either
constituent. Both are digest-checked before any provider call.

Scope: replay composition only. B2 items, the repeat-0 rule, the B1 artifact and its
handoff bytes, the task text, the sensory and resident models, the scorer, the expected
answers, the bounds, the ASICloud caps, normal live ingress behaviour and B2 grading
are all unchanged. This module performs no inference and never touches a provider.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

AMENDMENT_VERSION = "v2.2"

#: Serialisation rules. These MUST match ``ingress.pipe.route_image_with_text`` exactly,
#: or a replay would not reproduce the live payload it stands in for.
COMPOSITION_KWARGS = {"ensure_ascii": False, "sort_keys": True}
HUMAN_TEXT_KEY = "human_text"
SENSORY_HANDOFF_KEY = "sensory_handoff"

#: Frozen B1 repeat-0 handoff digests, unchanged from Amendment v2.1.
FROZEN_HANDOFF_SHA256 = {
    "ocr_count": "d55183d4daae008f7f034952a7e87e8fd803dbadd9ef3e03444d349f9997b0a3",
    "distractor_selection": "b6d1cd82e793179bab42fb838ab8878e414e9b6f5d1a81f1e63033a2cd7e2b7f",
    "multi_fact_composition": "e41d1d2e9c75e279d1c886ab2bb3cbf208271bd9b78e266ce246a80a3ae95237",
}

#: Frozen human instructions, digested from the existing benchmark items. These are the
#: same bytes Condition A delivered on its image+text runs.
FROZEN_HUMAN_TEXT_SHA256 = {
    "ocr_count": "2111a90408080e31fde2f5633043d5f603cdbbb47690ffea2ea8d67860db58a1",
    "distractor_selection": "d6bc2d9078222d72ae867b85fdb6f6f2c5586fc7be3e23334b5cf688f50f0fed",
    "multi_fact_composition": "c473668281ecb5df3c173dd89c0d6378a405fd5b15cf8833f12be7a3f6a49024",
}

REQUIRED_PROVENANCE_FIELDS = (
    "replayed_from",
    "origin_run_id",
    "original_image_sha256",
    "sensory_model",
    "handoff_payload_sha256",
    "human_text_sha256",
    "composed_payload_sha256",
)


class CompositionInvalid(ValueError):
    """A constituent did not match its frozen digest, or composition drifted."""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compose_replay_payload(*, human_text: str, handoff_payload: str) -> str:
    """Build the combined payload from two frozen constituents.

    Deterministic and offline: no image, no sensory runner, no provider, no network.
    The handoff arrives as the exact bytes B1 produced and is parsed back into the
    object the live route would have received from the sensory runner.
    """
    handoff = json.loads(handoff_payload)
    return json.dumps(
        {HUMAN_TEXT_KEY: human_text, SENSORY_HANDOFF_KEY: handoff},
        **COMPOSITION_KWARGS,
    )


def verify_constituents(
    *, item_id: str, human_text: str, handoff_payload: str
) -> dict[str, Any]:
    """Digest-check both constituents against their frozen values."""
    handoff_digest = sha256_text(handoff_payload)
    text_digest = sha256_text(human_text)
    expected_handoff = FROZEN_HANDOFF_SHA256.get(item_id)
    expected_text = FROZEN_HUMAN_TEXT_SHA256.get(item_id)
    return {
        "item_id": item_id,
        "handoff_payload_sha256": handoff_digest,
        "expected_handoff_sha256": expected_handoff,
        "handoff_matches": handoff_digest == expected_handoff,
        "human_text_sha256": text_digest,
        "expected_human_text_sha256": expected_text,
        "human_text_matches": text_digest == expected_text,
        "valid": handoff_digest == expected_handoff and text_digest == expected_text,
    }


def assert_constituents_valid(report: dict[str, Any]) -> None:
    """Hard stop before any provider inference if either constituent drifted."""
    if not report.get("valid"):
        raise CompositionInvalid(
            "B2 replay constituents do not match their frozen digests; the condition "
            f"is invalid and must not proceed to provider inference: {report}"
        )


def build_provenance(
    *,
    item_id: str,
    replayed_from: str,
    origin_run_id: str,
    original_image_sha256: str,
    sensory_model: str,
    human_text: str,
    handoff_payload: str,
    composed_payload: str,
) -> dict[str, Any]:
    """Provenance a B2 composition-replay record must carry."""
    return {
        "amendment": AMENDMENT_VERSION,
        "item_id": item_id,
        "replayed_from": replayed_from,
        "origin_run_id": origin_run_id,
        "original_image_sha256": original_image_sha256,
        "sensory_model": sensory_model,
        "handoff_payload_sha256": sha256_text(handoff_payload),
        "human_text_sha256": sha256_text(human_text),
        "composed_payload_sha256": sha256_text(composed_payload),
        "is_native_text_condition": False,
        "sensory_inference": False,
        "receipt_note": (
            "Ingress correctly records route=text_passthrough and "
            "sensory_inference=false for this replay event. No perception occurred "
            "during this run: the sensory constituent was produced earlier by the "
            "model named above, and the text constituent is the frozen benchmark "
            "instruction. The combined payload is a deterministic composition of the "
            "two and is byte-identical to what the live image+text route would build "
            "from that same handoff."
        ),
    }


def validate_provenance(provenance: dict[str, Any]) -> None:
    missing = [f for f in REQUIRED_PROVENANCE_FIELDS if not provenance.get(f)]
    if missing:
        raise CompositionInvalid(f"B2 record is missing provenance fields: {missing}")
    if provenance.get("is_native_text_condition"):
        raise CompositionInvalid(
            "a composition replay must never be recorded as a native text condition"
        )
    if provenance.get("sensory_inference"):
        raise CompositionInvalid(
            "a composition replay must never be recorded as having run perception"
        )


def specification() -> dict[str, Any]:
    return {
        "amendment": AMENDMENT_VERSION,
        "scope": "B2 replay composition only",
        "intervention": "same task text + alternate sensory evidence -> same resident",
        "constituents": ["frozen benchmark human instruction",
                         "frozen B1 repeat-0 sensory handoff"],
        "composition": f"{{{HUMAN_TEXT_KEY!r}: text, {SENSORY_HANDOFF_KEY!r}: handoff}}",
        "serialisation": dict(COMPOSITION_KWARGS),
        "byte_identity_invariant": (
            "the composed payload equals what the live image+text route would produce "
            "from the same handoff; it does NOT equal the raw B1 handoff"
        ),
        "raw_handoff_equality_claim_prohibited": True,
        "sensory_calls": 0,
        "live_ingress_changed": False,
        "b1_handoff_bytes_changed": False,
        "task_text_changed": False,
        "required_provenance_fields": list(REQUIRED_PROVENANCE_FIELDS),
        "unchanged": [
            "B2 items",
            "Amendment v2.1 repeat-0 rule",
            "B1 artifact",
            "B1 handoff bytes",
            "task text",
            "sensory model",
            "resident model",
            "scorer",
            "expected answers",
            "bounds",
            "ASICloud caps",
            "normal live ingress behaviour",
            "B2 grading",
        ],
    }
