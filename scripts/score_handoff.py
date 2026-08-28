"""Deterministic, pre-registered scorer for sensory handoffs.

Pure and offline: no network, no model, no LLM-as-judge, no post-hoc human
correction. Every rule below is fixed before any screening result is observed.

The sensory boundary is frozen for this benchmark. Its handoff has no dedicated
count field, so counts arrive as free-form prose ("Three small blue squares...") or
as an entity label ("three blue squares"). That is a property of the system under
test, recorded rather than repaired, and it is why count facts are scored by
co-occurrence within a single assertion string rather than by reading a field.

Verdicts
--------
``correct``   the rule below is satisfied
``incorrect`` the rule below is deterministically not satisfied
``unknown``   the scorer cannot decide deterministically; never guessed, never
              inferred by hand, and excluded from accuracy but reported as coverage
"""

from __future__ import annotations

import re
from typing import Any

CORRECT = "correct"
INCORRECT = "incorrect"
UNKNOWN = "unknown"

# Pre-declared number words. Counts in these stimuli never exceed five.
NUMBER_WORDS = {
    0: ("zero", "no"),
    1: ("one", "a single", "single"),
    2: ("two",),
    3: ("three",),
    4: ("four",),
    5: ("five",),
}

# Pre-declared relation lexical forms. A relation is scored ONLY through this map.
# Right-hand forms invert subject and object.
LEFT_OF_FORMS = (
    "left_of",
    "is_positioned_to_the_left_of",
    "is positioned to the left of",
    "is to the left of",
    "to the left of",
    "left of",
    "appears to the left of",
)
RIGHT_OF_FORMS = (
    "right_of",
    "is_positioned_to_the_right_of",
    "is positioned to the right of",
    "is to the right of",
    "to the right of",
    "right of",
    "appears to the right of",
)


def _assertion_strings(handoff: dict[str, Any]) -> list[str]:
    """Every free-form assertion the scorer is allowed to read.

    Deliberately narrow: literal observations and entity labels only. Interpretations
    and uncertainty are the model's commentary, not asserted observations.
    """
    obs = handoff.get("observation")
    if not isinstance(obs, dict):
        return []
    out: list[str] = []
    for value in obs.get("literal", []) or []:
        if isinstance(value, str):
            out.append(value)
    for entity in obs.get("entities", []) or []:
        if isinstance(entity, dict):
            label = entity.get("label")
            if isinstance(label, str):
                out.append(label)
    return out


def is_schema_conformant(handoff: Any) -> bool:
    """Minimal structural contract: an observation object with readable assertions."""
    if not isinstance(handoff, dict):
        return False
    obs = handoff.get("observation")
    if not isinstance(obs, dict):
        return False
    return isinstance(obs.get("literal"), list) or isinstance(obs.get("entities"), list)


def _score_token(fact: dict, strings: list[str]) -> str:
    """Correct iff the exact case-sensitive token appears in an assertion string."""
    return CORRECT if any(fact["value"] in s for s in strings) else INCORRECT


def _score_presence(fact: dict, strings: list[str]) -> str:
    """Correct iff colour and shape appear in the SAME assertion string."""
    colour, shape = fact["colour"].lower(), fact["shape"].lower()
    for s in strings:
        low = s.lower()
        if colour in low and shape in low:
            return CORRECT
    return INCORRECT


def _score_count(fact: dict, strings: list[str]) -> str:
    """Correct iff the count, colour and shape co-occur in one assertion string."""
    colour, shape = fact["colour"].lower(), fact["shape"].lower()
    value = int(fact["value"])
    words = NUMBER_WORDS.get(value, ())
    digit = re.compile(rf"(?<!\d){value}(?!\d)")
    for s in strings:
        low = s.lower()
        if colour not in low or shape not in low:
            continue
        if digit.search(low) or any(w in low for w in words):
            return CORRECT
    return INCORRECT


def _score_number(fact: dict, strings: list[str]) -> str:
    """Correct iff the visible numeral appears as a standalone number."""
    value = int(fact["value"])
    digit = re.compile(rf"(?<!\d){value}(?!\d)")
    words = NUMBER_WORDS.get(value, ())
    for s in strings:
        low = s.lower()
        if digit.search(low) or any(w in low for w in words):
            return CORRECT
    return INCORRECT


def _mentions(text: str, colour: str, shape: str) -> bool:
    low = (text or "").lower()
    return colour in low and shape in low


def _score_relation(fact: dict, handoff: dict[str, Any]) -> str:
    """Scored ONLY via the pre-declared predicate forms and structured fields.

    Returns ``unknown`` when no relation entry maps onto a declared form: the scorer
    refuses to interpret free prose here rather than guessing.
    """
    obs = handoff.get("observation")
    if not isinstance(obs, dict):
        return UNKNOWN
    relations = obs.get("relations")
    if not isinstance(relations, list):
        return UNKNOWN

    sc, ss = fact["subject_colour"].lower(), fact["subject_shape"].lower()
    oc, os_ = fact["object_colour"].lower(), fact["object_shape"].lower()
    mapped = False
    for rel in relations:
        if not isinstance(rel, dict):
            continue
        pred = str(rel.get("predicate", "")).lower().strip()
        subj = str(rel.get("subject", ""))
        obj = str(rel.get("object", ""))
        if pred in LEFT_OF_FORMS:
            mapped = True
            if _mentions(subj, sc, ss) and _mentions(obj, oc, os_):
                return CORRECT
        elif pred in RIGHT_OF_FORMS:
            mapped = True
            # Inverted: "B right of A" asserts "A left of B".
            if _mentions(obj, sc, ss) and _mentions(subj, oc, os_):
                return CORRECT
    return INCORRECT if mapped else UNKNOWN


_SCORERS = {
    "token": lambda f, s, h: _score_token(f, s),
    "shape_presence": lambda f, s, h: _score_presence(f, s),
    "shape_count": lambda f, s, h: _score_count(f, s),
    "number": lambda f, s, h: _score_number(f, s),
    "relation": lambda f, s, h: _score_relation(f, h),
}


def score_item(handoff: Any, facts: list[dict]) -> dict[str, Any]:
    """Score one handoff against one item's expected atomic facts.

    A non-conformant or absent handoff yields zero correct facts, with every fact
    marked ``incorrect`` rather than ``unknown``: a contract failure is evidence, not
    an absence of evidence.
    """
    conformant = is_schema_conformant(handoff)
    strings = _assertion_strings(handoff) if conformant else []

    verdicts = []
    for fact in facts:
        if not conformant:
            verdicts.append({"fact": fact, "verdict": INCORRECT})
            continue
        scorer = _SCORERS.get(fact["type"])
        verdict = scorer(fact, strings, handoff) if scorer else UNKNOWN
        verdicts.append({"fact": fact, "verdict": verdict})

    correct = sum(1 for v in verdicts if v["verdict"] == CORRECT)
    scoreable = sum(1 for v in verdicts if v["verdict"] != UNKNOWN)
    expected = len(facts)
    return {
        "schema_conformant": conformant,
        "verdicts": verdicts,
        "correct": correct,
        "scoreable": scoreable,
        "expected": expected,
        # Accuracy over facts the scorer could decide.
        "atomic_fact_accuracy": (correct / scoreable) if scoreable else None,
        # Yield over ALL expected facts -- the pre-registered selection metric.
        "atomic_fact_yield": correct / expected if expected else None,
        # How much of the expected fact set the scorer could decide at all.
        "scoring_coverage": scoreable / expected if expected else None,
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-call results into the pre-registered selection metrics."""
    correct = sum(r["correct"] for r in results)
    scoreable = sum(r["scoreable"] for r in results)
    expected = sum(r["expected"] for r in results)
    conformant = sum(1 for r in results if r["schema_conformant"])
    return {
        "calls": len(results),
        "correct_facts": correct,
        "scoreable_facts": scoreable,
        "expected_facts": expected,
        "atomic_fact_yield": (correct / expected) if expected else None,
        "atomic_fact_accuracy": (correct / scoreable) if scoreable else None,
        "scoring_coverage": (scoreable / expected) if expected else None,
        "schema_compliance_rate": (conformant / len(results)) if results else None,
    }


def repeat_stability(per_repeat: list[list[dict[str, Any]]]) -> float | None:
    """Fraction of items whose verdict vector is identical across all repeats."""
    if not per_repeat or len(per_repeat) < 2:
        return None
    items = len(per_repeat[0])
    if any(len(r) != items for r in per_repeat):
        return None
    stable = 0
    for idx in range(items):
        vectors = {
            tuple(v["verdict"] for v in repeat[idx]["verdicts"]) for repeat in per_repeat
        }
        if len(vectors) == 1:
            stable += 1
    return stable / items if items else None


def select_sensory_model(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the pre-registered selection rule, in order.

    1. highest schema-compliant atomic-fact yield (correct / all expected facts;
       a request failure or non-schema response contributes zero correct facts)
    2. tie -> highest schema-compliance rate
    3. tie -> highest repeat stability
    4. tie -> lowest mean output tokens
    5. residual tie -> lexicographically lowest exact model id

    No candidate is excluded for schema non-conformance on some images: that failure
    is benchmark evidence and is already penalised by rule 1.

    ``candidates`` entries must carry: model_id, atomic_fact_yield,
    schema_compliance_rate, repeat_stability, mean_output_tokens.
    """
    if not candidates:
        raise ValueError("no candidate sensory models to select from")

    def key(c: dict[str, Any]) -> tuple:
        return (
            -(c["atomic_fact_yield"] or 0.0),
            -(c["schema_compliance_rate"] or 0.0),
            -(c["repeat_stability"] or 0.0),
            c["mean_output_tokens"],
            c["model_id"],
        )

    return min(candidates, key=key)


SELECTION_RULE = (
    "1 highest schema-compliant atomic-fact yield (correct / all expected facts; "
    "a request failure or non-schema response contributes zero correct facts); "
    "2 tie -> highest schema-compliance rate; "
    "3 tie -> highest repeat stability; "
    "4 tie -> lowest mean output tokens; "
    "5 residual tie -> lexicographically lowest exact model id"
)
