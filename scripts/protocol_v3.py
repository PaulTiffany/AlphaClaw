"""Protocol v3 -- preregistration. Design only; no result is recorded here.

Two independent questions, deliberately kept apart. Their scores are never combined and
neither is used to tune the other.

**V3-A, failure attribution.** When AlphaClaw fails after the sensory boundary, is the
failure associated with information loss at the boundary, representation form,
instruction salience, one-turn scheduling, or output-channel / skill-selection
behaviour? The answer is not assumed: the interpretation matrix below is frozen before
any inference and every branch is reachable.

**V3-B, economic utility.** How much multimodal inference does perceive-once +
text-only-thereafter actually avoid, versus keeping multimodal inference resident for
every reasoning call?

Nothing in v2 is modified: not its artifacts, not its scorer, not its conclusions, not
the pinned OmegaClaw or ThreadKeeper.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import economics_v3
import representation_v3

PROTOCOL_VERSION = "v3"

# --- models -------------------------------------------------------------------
# Every model below is one already exercised in this repository. V3 introduces no new
# vendor and no new capability tier; that keeps v3 comparable to v2.

#: V3-A residents. Both are required: each reproduced a DIFFERENT observed v2 failure,
#: and a diagnostic that substituted another resident would not be the same diagnostic.
V3A_RESIDENT_MINIMAX = ("asicloud", "minimax/minimax-m3")
V3A_RESIDENT_GEMMA = ("openrouter", "google/gemma-4-26b-a4b-it")

#: V3-B uses ONE model for all three architectures. It is multimodal and also accepts
#: text-only input, so the multimodal and text-only arms share a model, a family and a
#: price schedule. That removes the model-price confound entirely: the only thing that
#: varies between arms is whether the image is attached to each call.
V3B_MODEL = ("openrouter", "qwen/qwen3.7-flash")

#: Never permitted as a resolved model anywhere in v3.
FORBIDDEN_MODELS = ("openrouter/free", "z-ai/glm-5.2")

# --- V3-A ---------------------------------------------------------------------

#: Diagnostic cases, taken only from already-observed v2 failures. This is a diagnostic
#: population, NOT a representative accuracy benchmark, and must never be reported as one.
V3A_CASES = (
    {
        "case_id": "A1",
        "item_id": "distractor_selection",
        "source_condition": "A:image_text",
        "resident": V3A_RESIDENT_MINIMAX,
        "observed_v2_failure": (
            "sensory evidence mechanically correct 4/4; correct token RED present "
            "internally; emitted as UNKNOWN_SKILL_CALL \"RED\"; no valid channel "
            "response. Reproduced under both dots and Qwen sensory handoffs."),
        "representations": representation_v3.VARIANTS,
    },
    {
        "case_id": "A2",
        "item_id": "number_arithmetic",
        "source_condition": "A:image_text",
        "resident": V3A_RESIDENT_GEMMA,
        "observed_v2_failure": (
            "correct token 19 present internally; emitted as UNKNOWN_SKILL_CALL \"19\"; "
            "no valid channel response."),
        "representations": representation_v3.VARIANTS,
    },
    {
        "case_id": "A3",
        "item_id": "number_arithmetic",
        "source_condition": "A:text_control",
        "resident": V3A_RESIDENT_GEMMA,
        "observed_v2_failure": (
            "task parsed correctly; the one permitted turn produced bookkeeping "
            "(pin task_goal) and a status message rather than the answer."),
        # A native text control has no sensory handoff, so representation does not apply.
        "representations": (),
    },
)

#: Turn-budget levels. Two only. One turn stays the architectural baseline; two turns is
#: a diagnostic control and is NOT the AlphaClaw population.
V3A_TURN_BUDGETS = (1, 2)
V3A_BASELINE_TURN_BUDGET = 1

#: Held fixed across every V3-A run unless a factor explicitly varies it.
V3A_HELD_FIXED = (
    "task",
    "task-relevant facts",
    "expected answer",
    "resident model",
    "provider",
    "OmegaClaw and ThreadKeeper pins",
    "stock Omega image",
    "output contract",
    "task instruction bytes (except where R4 varies task STRUCTURE, never the bytes)",
    "sensory evidence source (frozen v2 handoffs; no new sensory inference)",
)

#: Frozen before results. Every branch is reachable; none is privileged.
V3A_INTERPRETATION_MATRIX = (
    {"observation": "R1 FAIL and R2 PASS at the same turn budget",
     "reading": "evidence that representation richness/form affects the outcome"},
    {"observation": "R1 FAIL and R3 PASS with the same facts and budget",
     "reading": "evidence that representation form affects the outcome"},
    {"observation": "R1 FAIL and R4 PASS at the same turn budget",
     "reading": "evidence that explicit task structure affects the outcome"},
    {"observation": "one-turn FAIL and two-turn PASS on the same representation",
     "reading": "evidence that the one-turn scheduling constraint affects the outcome"},
    {"observation": ("correct internal token repeatedly present but emission invalid "
                     "across representations and budgets"),
     "reading": "evidence pointing toward output-channel / skill-selection behaviour"},
    {"observation": "all representations fail with missing or wrong task facts",
     "reading": ("inspect information preservation at the boundary BEFORE attributing "
                 "any downstream cause")},
)

V3A_INTERPRETATION_LIMIT = (
    "No branch of this matrix may be called a universal cause from one task, one "
    "resident, or one tranche."
)

# --- V3-B ---------------------------------------------------------------------

#: The task family. Depth is induced by the number of sequential reasoning CALLS, while
#: the perceived evidence stays constant -- which is exactly what lets one handoff serve
#: every depth.
V3B_TASK_FAMILY = {
    "name": "chained_accumulation",
    "generator": "deterministic; extends the existing stdlib PNG generator in a NEW "
                 "module so that every v2 item digest is untouched",
    "stimulus": "one image showing eight integers in a fixed left-to-right order",
    "task": "step i adds the i-th integer to the running total; after N steps reply "
            "with the running total, digits only",
    "ground_truth": "sum of the first N integers in the frozen order; mechanical",
    "llm_judge": False,
    "handoff_constant_across_depths": True,
    "depth_varies": "number of sequential resident calls, not the stimulus",
    "tuning_after_results": "prohibited",
}

V3B_ARCHITECTURES = economics_v3.ARCHITECTURES
V3B_DEPTHS = economics_v3.DEPTHS
V3B_ITEMS = 2
V3B_REPEATS = 1

#: E1 cannot run through the bounded controller: Omega is text-only and AlphaClaw must
#: never mutate outbound Omega provider bodies to attach images. All three arms are
#: therefore measured with ONE direct provider harness, held constant across arms, and
#: no Omega container is launched for V3-B. This is disclosed rather than papered over.
V3B_HARNESS_NOTE = (
    "E1/E2/E3 are measured with a single direct provider harness. E1 is not AlphaClaw "
    "and does not run Omega. Deployed AlphaClaw cost, where the text-only resident is a "
    "different model, is an ESTIMATE and is reported separately from measured call "
    "avoidance."
)

V3B_FAIRNESS_RULE = (
    "One model serves all three arms, so capability and price schedule are identical "
    "across arms and only input modality per call varies. Architecture-measured call "
    "avoidance is reported separately from any model-price-dependent dollar "
    "extrapolation, and cheap-vs-expensive model pairs are never presented as "
    "'AlphaClaw savings'."
)

# --- budgets ------------------------------------------------------------------
# V3 opens its OWN allocations. It does NOT raise, reuse or reinterpret the Protocol v2
# ASICloud cap, which stays exhausted at 42/42.

V3A_ASICLOUD_MAX_CALLS = 20          # A1: 4 runs x 2 + 4 runs x 3
V3A_OPENROUTER_MAX_CALLS = 25        # A2: 20, A3: 5
V3A_SENSORY_MAX_CALLS = 0            # frozen v2 handoffs only

V3B_MULTIMODAL_MAX_CALLS = 38        # E1 30 + E2 8
V3B_TEXT_MAX_CALLS = 60              # E2 30 + E3 30
V3B_MAX_CALLS = V3B_MULTIMODAL_MAX_CALLS + V3B_TEXT_MAX_CALLS

V3_MAX_INPUT_TOKENS = 520_000
V3_MAX_OUTPUT_TOKENS = 230_000
V3A_MAX_COST_USD = 0.50
V3B_MAX_COST_USD = 2.00
V3_MAX_COST_USD = 2.50

#: Any one of these halts the tranche or the case, before spending.
V3_STOP_CONDITIONS = (
    "any v2 artifact digest mismatch -> halt the entire tranche",
    "OmegaClaw or ThreadKeeper commit/byte pin mismatch -> halt the entire tranche",
    "stock Omega image id changed -> halt the entire tranche",
    "a representation leaks the item's exact expected answer -> halt that case",
    "a preflight invariant fails for a case -> that case makes no provider call",
    "any call cap reached -> halt that section",
    "any token or dollar cap reached -> halt that section",
    "provider availability failure -> record as evidence; no substitute, no retry",
    "scorer or v2 conclusions would need changing to make a result work -> halt",
)

V3_POLICY = (
    "no automatic model fallback",
    "no retry-until-pass",
    "provider availability failures remain evidence",
    "no prompt tuning after results",
    "no changing representation rules after observing results",
    "no broadening the v2 scorer retrospectively",
    "no LLM judge anywhere",
    "V3-A and V3-B scores are never combined",
    "neither section is used to tune the other",
    "V3-A is a diagnostic population, not a representative accuracy benchmark",
)


# --- derived plan -------------------------------------------------------------


def v3a_runs() -> list[dict[str, Any]]:
    """Every planned V3-A run. One row per (case, representation, turn budget)."""
    planned = []
    for case in V3A_CASES:
        variants = case["representations"] or (None,)
        for variant in variants:
            for turns in V3A_TURN_BUDGETS:
                planned.append({
                    "case_id": case["case_id"],
                    "item_id": case["item_id"],
                    "representation": variant,
                    "turn_budget": turns,
                    "provider": case["resident"][0],
                    "model": case["resident"][1],
                    "boot_calls": 1,
                    "max_episode_calls": turns,
                    "max_provider_calls": 1 + turns,
                    "sensory_calls": 0,
                })
    return planned


def v3a_call_budget() -> dict[str, int]:
    planned = v3a_runs()
    asicloud = sum(r["max_provider_calls"] for r in planned if r["provider"] == "asicloud")
    openrouter = sum(r["max_provider_calls"] for r in planned
                     if r["provider"] == "openrouter")
    return {
        "runs": len(planned),
        "asicloud_calls": asicloud,
        "openrouter_resident_calls": openrouter,
        "sensory_calls": 0,
        "asicloud_cap": V3A_ASICLOUD_MAX_CALLS,
        "openrouter_cap": V3A_OPENROUTER_MAX_CALLS,
    }


def v3b_call_budget() -> dict[str, int]:
    multimodal = text = 0
    for _ in range(V3B_ITEMS * V3B_REPEATS):
        for depth in V3B_DEPTHS:
            structure = economics_v3.expected_call_structure(depth)
            for architecture in V3B_ARCHITECTURES:
                multimodal += structure[architecture]["multimodal_calls"]
                text += structure[architecture]["text_calls"]
    return {
        "items": V3B_ITEMS,
        "repeats": V3B_REPEATS,
        "depths": list(V3B_DEPTHS),
        "multimodal_calls": multimodal,
        "text_calls": text,
        "total_calls": multimodal + text,
        "multimodal_cap": V3B_MULTIMODAL_MAX_CALLS,
        "text_cap": V3B_TEXT_MAX_CALLS,
        "total_cap": V3B_MAX_CALLS,
    }


def total_projected_calls() -> dict[str, int]:
    a, b = v3a_call_budget(), v3b_call_budget()
    return {
        "V3A_asicloud": a["asicloud_calls"],
        "V3A_openrouter_resident": a["openrouter_resident_calls"],
        "V3A_sensory": 0,
        "V3B_multimodal": b["multimodal_calls"],
        "V3B_text": b["text_calls"],
        "grand_total": (a["asicloud_calls"] + a["openrouter_resident_calls"]
                        + b["total_calls"]),
    }


def validate() -> None:
    """Fail loudly if the preregistration is internally inconsistent."""
    a, b = v3a_call_budget(), v3b_call_budget()
    if a["asicloud_calls"] > V3A_ASICLOUD_MAX_CALLS:
        raise ValueError("V3-A ASICloud plan exceeds its cap")
    if a["openrouter_resident_calls"] > V3A_OPENROUTER_MAX_CALLS:
        raise ValueError("V3-A OpenRouter plan exceeds its cap")
    if b["multimodal_calls"] > V3B_MULTIMODAL_MAX_CALLS:
        raise ValueError("V3-B multimodal plan exceeds its cap")
    if b["text_calls"] > V3B_TEXT_MAX_CALLS:
        raise ValueError("V3-B text plan exceeds its cap")
    if a["sensory_calls"] != 0:
        raise ValueError("V3-A must make no new sensory call")
    for _, model in (V3A_RESIDENT_MINIMAX, V3A_RESIDENT_GEMMA, V3B_MODEL):
        if model in FORBIDDEN_MODELS:
            raise ValueError(f"forbidden model in the v3 matrix: {model}")
    if V3A_BASELINE_TURN_BUDGET != 1:
        raise ValueError("the architectural baseline must remain one turn")
    if set(V3A_TURN_BUDGETS) != {1, 2}:
        raise ValueError("only one- and two-turn budgets are preregistered")


def specification() -> dict[str, Any]:
    """The full frozen v3 preregistration, for serialisation into the artifact."""
    validate()
    return {
        "protocol_version": PROTOCOL_VERSION,
        "status": "preregistration; no result recorded",
        "sections": {
            "V3A": {
                "question": (
                    "When AlphaClaw fails after the sensory boundary, is the failure "
                    "associated with information loss at the symbolic boundary, "
                    "representation form/richness, instruction salience, one-turn "
                    "scheduling, or output-channel / skill-selection behaviour?"),
                "population_note": ("diagnostic cases drawn from observed v2 failures; "
                                    "NOT a representative accuracy benchmark"),
                "cases": [
                    {**case, "resident_provider": case["resident"][0],
                     "resident_model": case["resident"][1],
                     "representations": list(case["representations"])}
                    for case in V3A_CASES],
                "representations": {
                    "R1": "exact current AlphaClaw payload, unchanged",
                    "R2": "only the mechanically required facts, same schema",
                    "R3": "the same required facts as deterministic sentences",
                    "R4": "the same required facts with task structure explicit",
                    "shared": ("every variant carries the same frozen task instruction "
                               "bytes and the same task-relevant information"),
                    "answer_leakage": "prohibited; checked case-sensitively per item",
                },
                "turn_budgets": list(V3A_TURN_BUDGETS),
                "baseline_turn_budget": V3A_BASELINE_TURN_BUDGET,
                "two_turn_role": "diagnostic control, not the AlphaClaw population",
                "held_fixed": list(V3A_HELD_FIXED),
                "instruction_position_receipt": {
                    "module": "scripts/instruction_receipt.py",
                    "records": ["exact instruction text", "character offsets",
                                ("order relative to Omega context, human task and "
                                 "symbolic evidence"),
                                "characters before and after",
                                "whole-request tokens where a receipt supplies them"],
                    "salience_score_reported": False,
                    "per_segment_tokens_available": False,
                },
                "outcomes": ["exact-match response", "valid send emission present",
                             "expected token present internally but not emitted",
                             "failure class under existing v2 semantics",
                             "boot calls", "episode calls",
                             "raw idle ticks (lifecycle observation only)",
                             "provider usage",
                             ("two-turn only: which turn first contains the correct "
                              "internal answer, and which first contains a valid "
                              "user-facing answer")],
                "interpretation_matrix": list(V3A_INTERPRETATION_MATRIX),
                "interpretation_limit": V3A_INTERPRETATION_LIMIT,
                "call_budget": v3a_call_budget(),
                "planned_runs": v3a_runs(),
            },
            "V3B": {
                "question": (
                    "For a task needing multimodal perception then iterative reasoning, "
                    "what does perceive-once + text-only-thereafter save versus keeping "
                    "multimodal inference resident for every reasoning call?"),
                "architectures": {
                    "E1": "multimodal-resident baseline; media available every call",
                    "E2": "AlphaClaw; one sensory inference, symbolic handoff reused",
                    "E3": "text-oracle control; facts supplied as text, not deployable",
                },
                "model": {"provider": V3B_MODEL[0], "model": V3B_MODEL[1],
                          "used_by": list(V3B_ARCHITECTURES)},
                "fairness_rule": V3B_FAIRNESS_RULE,
                "harness_note": V3B_HARNESS_NOTE,
                "task_family": V3B_TASK_FAMILY,
                "depths": list(V3B_DEPTHS),
                "expected_call_structure": economics_v3.expected_call_table(),
                "expected_call_structure_label": (
                    "architectural arithmetic, not an empirical result; the benchmark "
                    "verifies that actual receipts match it"),
                "primary_metric": "multimodal calls avoided per episode (model-independent)",
                "economic_metrics": ["multimodal calls", "text-only calls",
                                     "input tokens", "output tokens",
                                     "actual dollar cost from receipts",
                                     "cost per successful episode",
                                     "cost per correct answer",
                                     "latency if reliably receipt-derived",
                                     "exact-match success"],
                "cost_equations": {
                    "C_MM(N)": "N * C_multimodal",
                    "C_Alpha(N)": "C_multimodal + (N - 1) * C_text",
                    "Savings(N)": "(N - 1) * (C_multimodal - C_text)",
                    "fraction": "1 - C_Alpha(N) / C_MM(N)",
                    "stationary_limit": "1 - C_text / C_multimodal",
                    "status": "analytic expectations; receipts test the architecture",
                },
                "cost_labelling": {
                    "measured": "derived from provider receipts",
                    "estimated": "derived from catalog pricing; never called measured",
                },
                "success_adjusted": (
                    "cost per SUCCESSFUL episode is the primary economic comparison; an "
                    "architecture failing the frozen success criterion is reported but "
                    "never called economically superior"),
                "call_budget": v3b_call_budget(),
            },
        },
        "independence": ("V3-A and V3-B are separate experiments; their scores are "
                         "never combined and neither tunes the other"),
        "caps": {
            "V3A_asicloud_calls": V3A_ASICLOUD_MAX_CALLS,
            "V3A_openrouter_resident_calls": V3A_OPENROUTER_MAX_CALLS,
            "V3A_sensory_calls": V3A_SENSORY_MAX_CALLS,
            "V3B_multimodal_calls": V3B_MULTIMODAL_MAX_CALLS,
            "V3B_text_calls": V3B_TEXT_MAX_CALLS,
            "V3B_total_calls": V3B_MAX_CALLS,
            "max_input_tokens": V3_MAX_INPUT_TOKENS,
            "max_output_tokens": V3_MAX_OUTPUT_TOKENS,
            "V3A_max_cost_usd": V3A_MAX_COST_USD,
            "V3B_max_cost_usd": V3B_MAX_COST_USD,
            "max_cost_usd": V3_MAX_COST_USD,
            "v2_asicloud_allocation": ("separate and untouched; v2 remains exhausted at "
                                       "42/42 and its cap is NOT raised"),
        },
        "total_projected_calls": total_projected_calls(),
        "scoring": {
            "criterion": "exact match under the already-frozen v2 task contracts",
            "failure_decomposition": "scripts/analyze_condition_a.py, unchanged",
            "sensory_scorer": "scripts/score_handoff.py, unchanged and not broadened",
            "new_scorer_introduced": False,
            "llm_judge": False,
        },
        "policy": list(V3_POLICY),
        "stop_conditions": list(V3_STOP_CONDITIONS),
        "unchanged_from_v2": [
            "all v2 artifacts", "the v2 scorer and its relation lexicon",
            "the v2 conclusions", "pinned OmegaClaw", "pinned ThreadKeeper",
            "the stock Omega image", "the sensory boundary",
            "the v2 ASICloud allocation",
        ],
    }
