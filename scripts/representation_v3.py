"""Protocol v3 deterministic representation transforms (V3-A factors R1-R4).

Pure, offline and total: no model, no network, no LLM summariser, no randomness. The
same fact set always renders to the same bytes, so a representation cannot be quietly
tuned after seeing a result.

Every variant carries the SAME task-relevant information and the SAME frozen task
instruction bytes. Only the *form* differs. That is the whole point of V3-A: it isolates
representation form from information content.

``R1`` full symbolic      -- the exact current AlphaClaw payload, unchanged
``R2`` minimal symbolic   -- only the mechanically required facts, same schema
``R3`` plain language     -- the same required facts as deterministic sentences
``R4`` task-structured    -- the same required facts, task structure made explicit

Answer leakage
--------------
No variant may contain the item's exact ``expected_answer`` string. That check is
case-sensitive and deliberately narrow: a required fact may legitimately mention a
colour word ("red"), while the expected answer token ("RED") must never appear. See
``leaks_answer``.
"""

from __future__ import annotations

import json
import re
from typing import Any

R1_FULL_SYMBOLIC = "R1_full_symbolic"
R2_MINIMAL_SYMBOLIC = "R2_minimal_symbolic"
R3_PLAIN_LANGUAGE = "R3_plain_language"
R4_TASK_STRUCTURED = "R4_task_structured"

VARIANTS = (R1_FULL_SYMBOLIC, R2_MINIMAL_SYMBOLIC,
            R3_PLAIN_LANGUAGE, R4_TASK_STRUCTURED)

#: Serialisation held identical to the live ingress route, so R1 reproduces v2 bytes.
SERIALISATION = {"ensure_ascii": False, "sort_keys": True}

#: Frozen count words. Counts in this benchmark family never exceed five.
COUNT_WORDS = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}

#: Frozen relation phrasing for R3. Rendering only -- this is NOT the scorer lexicon and
#: must never be used to widen it.
RELATION_PHRASES = {
    "left_of": "to the left of",
    "right_of": "to the right of",
}


class RepresentationError(ValueError):
    """A transform could not be produced deterministically."""


def required_facts(item: dict[str, Any]) -> list[dict[str, Any]]:
    """The mechanically required facts for an item: its frozen fact list, verbatim."""
    return [dict(fact) for fact in item["facts"]]


def _plural(word: str, count: int) -> str:
    return word if count == 1 else f"{word}s"


def render_fact_sentence(fact: dict[str, Any]) -> str:
    """One fact -> one deterministic English sentence. No new information."""
    kind = fact["type"]
    if kind == "shape_presence":
        return f"A {fact['colour']} {fact['shape']} is present."
    if kind == "shape_count":
        count = fact["value"]
        word = COUNT_WORDS.get(count, str(count))
        verb = "is" if count == 1 else "are"
        return f"There {verb} {word} {fact['colour']} {_plural(fact['shape'], count)}."
    if kind == "token":
        return f"The text {fact['value']} is shown."
    if kind == "number":
        return f"The number {fact['value']} is shown."
    if kind == "relation":
        phrase = RELATION_PHRASES.get(fact["predicate"])
        if phrase is None:
            raise RepresentationError(
                f"no frozen phrasing for relation predicate {fact['predicate']!r}")
        return (f"The {fact['subject_colour']} {fact['subject_shape']} is {phrase} "
                f"the {fact['object_colour']} {fact['object_shape']}.")
    raise RepresentationError(f"no frozen rendering for fact type {kind!r}")


def plain_language(facts: list[dict[str, Any]]) -> str:
    """Render the fact list in its frozen order. Deterministic and order-preserving."""
    return " ".join(render_fact_sentence(fact) for fact in facts)


def render(
    variant: str,
    *,
    human_text: str,
    facts: list[dict[str, Any]] | None = None,
    full_handoff: dict[str, Any] | None = None,
) -> str:
    """Produce the resident-facing payload for one representation variant.

    ``human_text`` is the frozen task instruction and is carried unchanged by every
    variant, so instruction bytes are never an uncontrolled difference.
    """
    if variant not in VARIANTS:
        raise RepresentationError(f"unknown representation variant {variant!r}")

    if variant == R1_FULL_SYMBOLIC:
        if full_handoff is None:
            raise RepresentationError("R1 requires the frozen full sensory handoff")
        return json.dumps({"human_text": human_text,
                           "sensory_handoff": full_handoff}, **SERIALISATION)

    if facts is None:
        raise RepresentationError(f"{variant} requires the required-fact list")

    if variant == R2_MINIMAL_SYMBOLIC:
        return json.dumps({"human_text": human_text,
                           "symbolic_facts": facts}, **SERIALISATION)
    if variant == R3_PLAIN_LANGUAGE:
        return json.dumps({"human_text": human_text,
                           "observations_text": plain_language(facts)}, **SERIALISATION)
    # R4: same facts, task structure made explicit. No answer, no extra instruction.
    return json.dumps({"task_instruction": human_text,
                       "observations": facts}, **SERIALISATION)


#: Amendment v3.1. A bare substring test is wrong for short numeric answers: the frozen
#: v2 payload for ``number_arithmetic`` contains "19" inside the image digest
#: ...c197e29bfb, which states nothing. Leakage means the answer appears as a STANDALONE
#: token, so the test is anchored on word boundaries. Still case-sensitive, still
#: mechanical, still applied to every variant including R1. Discovered by preflight
#: before any v3 provider call; no representation was changed.
LEAK_CHECK_VERSION = "v3.1-word-boundary"


def leaks_answer(payload: str, expected_answer: str) -> bool:
    """True if the expected answer appears as a standalone token in the payload.

    Case-sensitive on purpose: ``RED`` leaking is a failure, while a required fact
    naming the colour ``red`` is the information the task legitimately needs.

    Word-anchored on purpose: ``19`` inside a hex digest is not a stated answer, while
    ``19`` as its own token is.
    """
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(expected_answer)}(?![A-Za-z0-9])",
                     payload) is not None


def transform_manifest(
    *, item_id: str, variant: str, human_text: str, payload: str
) -> dict[str, Any]:
    """Receipt describing one produced representation, for the run record."""
    import hashlib

    return {
        "item_id": item_id,
        "variant": variant,
        "human_text_sha256": hashlib.sha256(human_text.encode("utf-8")).hexdigest(),
        "payload_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload_chars": len(payload),
        "deterministic": True,
        "llm_summariser_used": False,
    }
