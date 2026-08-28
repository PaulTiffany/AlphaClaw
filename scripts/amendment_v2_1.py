"""Protocol Amendment v2.1 -- B2 replay-source selection.

Protocol v2 fixed the B2 item list but failed to specify which of the two B1 repeats
supplies the single replay handoff. B1 has already been run and its artifact is
immutable, so the rule below is deliberately blind to every result: it depends only on
``repeat_index``, never on scorer output, atomic-fact accuracy, apparent quality, or
the downstream expected answer.

Rule
----
For every B2 item, replay B1 ``repeat_index = 0`` only.

- If repeat 0 produced a usable schema-conformant symbolic handoff, that exact payload
  is the B2 replay source.
- If repeat 0 did not produce a usable schema-conformant handoff, that B2 item is
  **unavailable** under v2.1.
- There is **no fall-through to repeat 1**. Repeat 1 remains B1 replication evidence
  only and can never replace repeat 0 for B2.

Scope: this amendment changes replay-source selection and nothing else. Stimuli, the
Qwen and MiniMax model conditions, the B2 item list, the scorer, the sensory boundary,
the B1 results, the replay bytes and the ASICloud caps are all unchanged.
"""

from __future__ import annotations

from typing import Any

AMENDMENT_VERSION = "v2.1"

# The single permitted replay source. Not a preference or a default -- the only value.
B2_REPLAY_REPEAT_INDEX = 0

# Selection may consult these fields and no others.
PERMITTED_SELECTION_FIELDS = ("item_id", "repeat_index", "handoff_payload", "schema_conformant")

# Consulting any of these would make selection quality-based, which is prohibited.
PROHIBITED_SELECTION_FIELDS = (
    "correct",
    "scoreable",
    "expected",
    "verdicts",
    "atomic_fact_yield",
    "atomic_fact_accuracy",
    "scoring_coverage",
    "expected_answer",
    "output_tokens",
)


class B2SourceUnavailable(RuntimeError):
    """Repeat 0 produced no usable schema-conformant handoff for this item."""


def _repeat_zero(b1_calls: list[dict[str, Any]], item_id: str) -> dict[str, Any] | None:
    for call in b1_calls:
        if call.get("item_id") == item_id and call.get("repeat_index") == B2_REPLAY_REPEAT_INDEX:
            return call
    return None


def is_usable_source(call: dict[str, Any] | None) -> bool:
    """Usable means: exists, schema-conformant, and carries a replayable payload.

    Deliberately says nothing about how well it scored.
    """
    if call is None:
        return False
    return bool(call.get("schema_conformant")) and bool(call.get("handoff_payload"))


def select_b2_source(b1_calls: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
    """Return the repeat-0 replay source for one B2 item, or raise.

    Never inspects scores, and never falls through to repeat 1.
    """
    call = _repeat_zero(b1_calls, item_id)
    if not is_usable_source(call):
        raise B2SourceUnavailable(
            f"{item_id}: B1 repeat {B2_REPLAY_REPEAT_INDEX} produced no usable "
            "schema-conformant handoff; the item is unavailable under v2.1 and must "
            "not fall through to repeat 1"
        )
    assert call is not None
    return {
        "item_id": call["item_id"],
        "repeat_index": call["repeat_index"],
        "sensory_model": call.get("requested_model"),
        "resolved_model": call.get("resolved_model"),
        "source_sha256": call.get("source_sha256"),
        "handoff_payload": call["handoff_payload"],
        "handoff_payload_sha256": call.get("handoff_payload_sha256"),
    }


def build_b2_plan(b1_calls: list[dict[str, Any]], b2_items: tuple[str, ...]) -> dict[str, Any]:
    """Plan every B2 item, recording unavailability rather than substituting."""
    selected, unavailable = [], []
    for item_id in b2_items:
        try:
            selected.append(select_b2_source(b1_calls, item_id))
        except B2SourceUnavailable as exc:
            unavailable.append({"item_id": item_id, "reason": str(exc)})
    return {
        "amendment": AMENDMENT_VERSION,
        "rule": (
            f"replay B1 repeat_index = {B2_REPLAY_REPEAT_INDEX} only; no fall-through "
            "to repeat 1; selection is independent of score, accuracy, apparent quality "
            "and expected answer"
        ),
        "selected": selected,
        "unavailable": unavailable,
    }


def specification() -> dict[str, Any]:
    return {
        "amendment": AMENDMENT_VERSION,
        "scope": "B2 replay-source selection only",
        "b2_replay_repeat_index": B2_REPLAY_REPEAT_INDEX,
        "quality_based_selection_prohibited": True,
        "fall_through_to_repeat_1_prohibited": True,
        "repeat_1_role": "B1 replication evidence only; can never replace repeat 0 for B2",
        "permitted_selection_fields": list(PERMITTED_SELECTION_FIELDS),
        "prohibited_selection_fields": list(PROHIBITED_SELECTION_FIELDS),
        "unchanged": [
            "stimuli",
            "Qwen sensory model condition",
            "MiniMax resident model condition",
            "B2 item list",
            "scorer",
            "sensory boundary",
            "B1 results",
            "replay bytes",
            "ASICloud caps",
            "all other v2 conditions",
        ],
    }
