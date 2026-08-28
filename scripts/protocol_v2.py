"""Protocol v2 -- preregistered model-variety tranche.

Chronology
----------
v1    established the controlled six-item benchmark, the frozen sensory boundary, the
      deterministic scorer, and a three-candidate sensory screen with a selection rule.
v1.1  added provider-availability recovery only.
v2    adds explicit model-variety experimental conditions and replay provenance.

v2 is preregistered before any Qwen sensory, paid-Gemma resident, or new ASICloud
benchmark result exists.

Scope
-----
Sensory and resident models are **experimental conditions, not tournament candidates**.
The v1/v1.1 selection rules remain historically intact but do not select among v2
conditions, and no ranking is produced here.

Frozen and unchanged by v2: the six benchmark items and their image, rule and answer
digests; the ground truth; the sensory SYSTEM_PROMPT and normalisation; the scorer and
its scoring-coverage semantics; the Alpha envelope; stock pinned Omega; the bounds;
boot readiness; the boot-turn barrier; drain ordering; gateway accounting; and the
failure classification from v1/v1.1. The v1 and v1.1 artifacts are not modified.
"""

from __future__ import annotations

PROTOCOL_VERSION = "v2"

# --- named model conditions (exact identifiers; no fallbacks, no substitutes) ------
SENSORY_PRIMARY = "dots-studio/dots-3-note-preview:free"
SENSORY_ALTERNATE = "qwen/qwen3.7-flash"
RESIDENT_PRIMARY_PROVIDER = "asicloud"
RESIDENT_PRIMARY_MODEL = "minimax/minimax-m3"
RESIDENT_ALTERNATE_PROVIDER = "openrouter"
RESIDENT_ALTERNATE_MODEL = "google/gemma-4-26b-a4b-it"

# Explicitly barred. An unavailable named condition is recorded as evidence; it is
# never replaced by another endpoint, and no automatic fallback exists.
FORBIDDEN_MODELS = frozenset(
    {
        "openrouter/free",                # nondeterministic router
        "google/gemma-4-26b-a4b-it:free",  # exhausted free endpoint (v1 + v1.1)
        "google/gemma-4-31b-it:free",      # exhausted free endpoint (v1 + v1.1)
    }
)

# --- preselected item lists, fixed before any v2 result exists --------------------
B2_ITEMS = ("ocr_count", "distractor_selection", "multi_fact_composition")

# (item_id, condition) -- condition is "text_control" or "image_text"
C_CONDITIONS = (
    ("number_arithmetic", "text_control"),
    ("ocr_count", "image_text"),
    ("number_arithmetic", "image_text"),
)

# --- call caps -------------------------------------------------------------------
# Derived from the v1 receipt maxima: boot 1432 in / 134 out, episode capped at
# 4500 in / 900 out, i.e. 5932 in and 1034 out per bounded run, over 21 ASICloud runs
# (18 in condition A, 3 in condition B2).
ASICLOUD_MAX_CALLS = 42          # v1 cap was 36; raised explicitly by this amendment
ASICLOUD_MAX_INPUT_TOKENS = 124_572
ASICLOUD_MAX_OUTPUT_TOKENS = 21_714

OPENROUTER_PAID_CALLS = 18       # B1 sensory 12 + C resident 6
OPENROUTER_FREE_CALLS = 12       # condition A sensory, dots free endpoint

# Projection only, from current catalog pricing. Not a guaranteed invoice.
PROJECTED_OPENROUTER_COST_USD = 0.0054

CONDITIONS = (
    {
        "condition_id": "A",
        "name": "Primary Alpha benchmark",
        "sensory_model": SENSORY_PRIMARY,
        "resident_provider": RESIDENT_PRIMARY_PROVIDER,
        "resident_model": RESIDENT_PRIMARY_MODEL,
        "items": "all six items across the existing matched conditions",
        "sensory_calls": 12,
        "boot_calls": 18,
        "episode_calls": 18,
        "resident_billing": "asicloud",
        "grading_target": (
            "exact-match for text control and image+text; sensory transformation for "
            "image-only"
        ),
        "question": (
            "Does the bounded architecture work end to end under the sponsored "
            "HyperSprint condition?"
        ),
        "uses_replay": False,
    },
    {
        "condition_id": "B1",
        "name": "Sensory substitution",
        "sensory_model": SENSORY_ALTERNATE,
        "resident_provider": None,
        "resident_model": None,
        "items": "all six images, two repeats",
        "sensory_calls": 12,
        "boot_calls": 0,
        "episode_calls": 0,
        "resident_billing": None,
        "grading_target": "frozen 21-atomic-fact sensory scorer and scoring coverage",
        "question": (
            "Is the frozen sensory boundary portable across a distinct sensory-model "
            "family?"
        ),
        "uses_replay": False,
    },
    {
        "condition_id": "B2",
        "name": "Alternate sensory handoff downstream",
        "sensory_model": SENSORY_ALTERNATE,
        "resident_provider": RESIDENT_PRIMARY_PROVIDER,
        "resident_model": RESIDENT_PRIMARY_MODEL,
        "items": list(B2_ITEMS),
        "sensory_calls": 0,
        "boot_calls": 3,
        "episode_calls": 3,
        "resident_billing": "asicloud",
        "grading_target": "exact-match under the already-frozen task contracts",
        "question": (
            "Does an alternate sensory model produce a symbolic handoff sufficient for "
            "the same fixed MiniMax resident reasoner?"
        ),
        "uses_replay": True,
        "replay_source": "B1",
    },
    {
        "condition_id": "C",
        "name": "Resident substitution",
        "sensory_model": SENSORY_PRIMARY,
        "resident_provider": RESIDENT_ALTERNATE_PROVIDER,
        "resident_model": RESIDENT_ALTERNATE_MODEL,
        "items": [f"{item}:{cond}" for item, cond in C_CONDITIONS],
        "sensory_calls": 0,
        "boot_calls": 3,
        "episode_calls": 3,
        "resident_billing": "openrouter",
        "grading_target": "exact-match",
        "question": "Same symbolic evidence -> different resident model.",
        "uses_replay": True,
        "replay_source": "A",
    },
)

# --- replay provenance -----------------------------------------------------------
# A replay is NOT a native text benchmark condition. Mechanically it routes through
# .json text passthrough, so the ingress receipt correctly records
# route=text_passthrough, sensory_inference=false, and the digest of the replay JSON.
# That receipt is accurate for the replay event and is never rewritten to pretend
# perception occurred. These provenance fields carry the missing context instead.
REPLAY_PROVENANCE_FIELDS = (
    "replayed_from",
    "origin_run_id",
    "original_image_sha256",
    "sensory_model",
    "handoff_payload_sha256",
)


def asicloud_call_budget() -> dict[str, int]:
    """Per-condition ASICloud usage; must total exactly ASICLOUD_MAX_CALLS."""
    per = {
        c["condition_id"]: c["boot_calls"] + c["episode_calls"]
        for c in CONDITIONS
        if c["resident_billing"] == "asicloud"
    }
    per["total"] = sum(per.values())
    return per


def openrouter_call_budget() -> dict[str, int]:
    paid = sum(
        c["sensory_calls"] for c in CONDITIONS if c["sensory_model"] == SENSORY_ALTERNATE
    ) + sum(
        c["boot_calls"] + c["episode_calls"]
        for c in CONDITIONS
        if c["resident_billing"] == "openrouter"
    )
    free = sum(
        c["sensory_calls"] for c in CONDITIONS if c["sensory_model"] == SENSORY_PRIMARY
    )
    return {"paid": paid, "free": free}


def validate() -> None:
    """Fail loudly if the encoded matrix drifts from the preregistered caps."""
    budget = asicloud_call_budget()
    if budget["total"] != ASICLOUD_MAX_CALLS:
        raise ValueError(
            f"ASICloud matrix totals {budget['total']}, cap is {ASICLOUD_MAX_CALLS}"
        )
    named = {
        SENSORY_PRIMARY,
        SENSORY_ALTERNATE,
        RESIDENT_PRIMARY_MODEL,
        RESIDENT_ALTERNATE_MODEL,
    }
    if named & FORBIDDEN_MODELS:
        raise ValueError("a v2 condition names a forbidden model")
    for condition in CONDITIONS:
        if condition["uses_replay"] and condition["sensory_calls"] != 0:
            raise ValueError(
                f"{condition['condition_id']} replays evidence and must make no "
                "sensory call"
            )


def specification() -> dict:
    """The full frozen v2 specification, for serialisation into the artifact."""
    validate()
    return {
        "protocol_version": PROTOCOL_VERSION,
        "chronology": {
            "v1": "controlled six-item benchmark, frozen boundary, scorer, sensory screen",
            "v1.1": "provider-availability recovery only",
            "v2": "explicit model-variety conditions and replay provenance",
            "preregistered_before": (
                "any Qwen sensory, paid-Gemma resident, or new ASICloud benchmark result"
            ),
        },
        "models": {
            "sensory_primary": SENSORY_PRIMARY,
            "sensory_alternate": SENSORY_ALTERNATE,
            "resident_primary": {
                "provider": RESIDENT_PRIMARY_PROVIDER,
                "model": RESIDENT_PRIMARY_MODEL,
            },
            "resident_alternate": {
                "provider": RESIDENT_ALTERNATE_PROVIDER,
                "model": RESIDENT_ALTERNATE_MODEL,
            },
            "forbidden": sorted(FORBIDDEN_MODELS),
            "note": (
                "Experimental conditions, not tournament candidates. v1/v1.1 selection "
                "rules remain historically intact but do not select among v2 conditions. "
                "An unavailable named condition is recorded as evidence and never "
                "substituted."
            ),
        },
        "conditions": list(CONDITIONS),
        "preselected_items": {"B2": list(B2_ITEMS), "C": [list(c) for c in C_CONDITIONS]},
        "caps": {
            "asicloud_max_calls": ASICLOUD_MAX_CALLS,
            "asicloud_previous_cap": 36,
            "asicloud_max_input_tokens": ASICLOUD_MAX_INPUT_TOKENS,
            "asicloud_max_output_tokens": ASICLOUD_MAX_OUTPUT_TOKENS,
            "asicloud_per_condition": asicloud_call_budget(),
            "openrouter": openrouter_call_budget(),
            "projected_openrouter_cost_usd": PROJECTED_OPENROUTER_COST_USD,
            "cost_note": "Projection from current catalog pricing, not a guaranteed invoice.",
        },
        "replay": {
            "is_native_text_condition": False,
            "receipt_semantics": (
                "route=text_passthrough, sensory_inference=false, source digest of the "
                "replay JSON. Accurate for the replay event; never rewritten to pretend "
                "sensory inference occurred."
            ),
            "required_provenance_fields": list(REPLAY_PROVENANCE_FIELDS),
            "byte_identity_required_between": [
                "original symbolic payload",
                "replay input payload",
                "payload embedded in the resulting Alpha envelope",
            ],
            "on_identity_failure": "condition is invalid; stop before provider inference",
        },
        "policy": {
            "retry_until_pass": False,
            "availability_failures_are_evidence": True,
            "automatic_fallback_model": False,
            "substitute_on_unavailable": False,
        },
    }
