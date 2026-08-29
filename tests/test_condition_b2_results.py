"""Protocol v2 Condition B2 -- frozen results and paired A/B2 contrast.

Offline. No network, no container, no provider call, no new scorer.

B2 replays the frozen B1 repeat-0 handoffs, composed under Amendment v2.2 with the
frozen benchmark instruction, into the same MiniMax resident. The controlled contrast
against Condition A image+text is: same task instruction + different sensory-model
handoff + same resident.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


a21 = _load("amendment_v2_1_b2", SCRIPTS / "amendment_v2_1.py")
a22 = _load("amendment_v2_2_b2", SCRIPTS / "amendment_v2_2.py")
v2 = _load("protocol_v2_b2", SCRIPTS / "protocol_v2.py")
scorer = _load("score_handoff_b2", SCRIPTS / "score_handoff.py")

ARTIFACT = ROOT / "benchmark" / "benchmark-v2-B2.json"
ARTIFACT_SHA = "8b6cc4557b27c8cc2acf7803ca05293b0fd39ca1fe1cc6f89dbe838045fd7d48"
A_SHA = "644f36e406df5520f54e6bcb706b891e9dd1ff9094c6c0d59cfb305e68be65ea"
B1_SHA = "847828d469d60269a289f5183d07a69c6afc4c123ef1ad51346490e778e0ab14"

FAILED_ITEM = "distractor_selection"
PASSED_ITEMS = ("ocr_count", "multi_fact_composition")


@pytest.fixture(scope="module")
def data():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def runs(data):
    return {r["item_id"]: r for r in data["runs"]}


@pytest.fixture(scope="module")
def condition_a():
    raw = json.loads((ROOT / "benchmark" / "benchmark-v2-A.json").read_text(encoding="utf-8"))
    return {r["item_id"]: r for r in raw["runs"] if r["condition"] == "image_text"}


@pytest.fixture(scope="module")
def items():
    raw = json.loads((ROOT / "benchmark" / "items.json").read_text(encoding="utf-8"))
    return {i["item_id"]: i for i in raw["items"]}


# --- frozen artifacts ---------------------------------------------------------


def test_artifact_digest_is_frozen() -> None:
    assert hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() == ARTIFACT_SHA


def test_upstream_artifacts_unchanged() -> None:
    for name, expected in (("benchmark-v2-A.json", A_SHA),
                           ("screening-v2-B1.json", B1_SHA)):
        assert hashlib.sha256(
            (ROOT / "benchmark" / name).read_bytes()).hexdigest() == expected


def test_three_runs_under_both_amendments(data) -> None:
    assert data["condition_id"] == "B2"
    assert data["amendments"] == ["v2.1", "v2.2"]
    assert data["attempted_runs"] == 3
    assert len(data["runs"]) == 3
    assert {r["item_id"] for r in data["runs"]} == set(v2.B2_ITEMS)


# --- zero new perception ------------------------------------------------------


def test_zero_new_sensory_calls(data, runs) -> None:
    assert data["new_sensory_calls"] == 0
    for run in runs.values():
        ingress = run["manifest"]["ingress"]
        assert ingress["route"] == "text_passthrough"
        assert ingress["sensory_inference"] is False
        assert "sensory_trace" not in ingress


def test_receipts_were_not_rewritten_to_fake_perception(runs) -> None:
    """The ingress receipt stays truthful; provenance supplies the missing context."""
    for item_id, run in runs.items():
        provenance = run["provenance"]
        assert provenance["is_native_text_condition"] is False
        assert provenance["sensory_inference"] is False
        assert provenance["sensory_model"] == v2.SENSORY_ALTERNATE
        assert provenance["replayed_from"] == "B1"
        for field in a22.REQUIRED_PROVENANCE_FIELDS:
            assert provenance[field], (item_id, field)


# --- the nine pre-call checks -------------------------------------------------


def test_every_run_passed_all_nine_checks_before_its_provider_call(runs) -> None:
    for item_id, run in runs.items():
        assert run["all_checks_passed"] is True, item_id
        assert run["provider_call_made"] is True
        assert all(run["checks"].values()), (item_id, run["checks"])
        assert run["repeat_index"] == a21.B2_REPLAY_REPEAT_INDEX == 0


def test_recorded_digests_match_the_preregistered_constituents(runs) -> None:
    for item_id, run in runs.items():
        assert run["handoff_payload_sha256"] == a22.FROZEN_HANDOFF_SHA256[item_id]
        assert run["human_text_sha256"] == a22.FROZEN_HUMAN_TEXT_SHA256[item_id]


def test_delivered_envelope_carried_the_composed_payload(runs) -> None:
    """Not merely proven beforehand -- the controller's own envelope is checked."""
    for item_id, run in runs.items():
        assert run["envelope_matches_composed"] is True, item_id
        assert run["envelope_payload_sha256"] == run["composed_payload_sha256"]
        assert run["envelope_equals_live"] is True


# --- bounds -------------------------------------------------------------------


def test_every_run_obeyed_one_boot_and_one_episode(runs) -> None:
    for item_id, run in runs.items():
        usage = run["manifest"]["usage_by_phase"]
        assert usage["boot"]["calls"] == 1, item_id
        assert usage["episode"]["calls"] == 1, item_id
        gateway = run["manifest"]["provider_gateway"]
        assert gateway["max_boot_calls"] == 1
        assert gateway["max_episode_calls"] == 1
        assert gateway["fatal_error"] is None


def test_cumulative_asicloud_usage_exhausts_the_allocation_exactly(runs) -> None:
    """A + B2 consume the ASICloud allocation exactly: 36 + 6 == 42 == the cap."""
    def total(records):
        calls = tokens_in = tokens_out = 0
        for record in records:
            usage = (record.get("manifest") or {}).get("usage_by_phase") or {}
            for phase in ("boot", "episode"):
                block = usage.get(phase, {})
                calls += block.get("calls", 0)
                tokens_in += block.get("input_tokens", 0)
                tokens_out += block.get("output_tokens", 0)
        return calls, tokens_in, tokens_out

    whole_a = json.loads(
        (ROOT / "benchmark" / "benchmark-v2-A.json").read_text(encoding="utf-8"))["runs"]
    a_calls, a_in, a_out = total(whole_a)
    b_calls, b_in, b_out = total(runs.values())

    assert a_calls == 36
    assert b_calls == 6
    assert a_calls + b_calls == 42
    assert a_calls + b_calls == v2.ASICLOUD_MAX_CALLS
    assert a_in + b_in <= v2.ASICLOUD_MAX_INPUT_TOKENS
    assert a_out + b_out <= v2.ASICLOUD_MAX_OUTPUT_TOKENS


def test_condition_c_is_on_a_separate_openrouter_ledger() -> None:
    """Ledger 2. C bills OpenRouter, so it is outside the ASICloud allocation.

    An exhausted ASICloud allocation means no further ASICloud condition may run without
    an amendment. It says nothing about a condition metered on a different path.
    """
    frozen = json.loads(
        (ROOT / "benchmark" / "protocol-v2.json").read_text(encoding="utf-8"))
    condition_c = next(c for c in frozen["conditions"] if c["condition_id"] == "C")

    # C's own ledger, as preregistered
    assert condition_c["resident_provider"] == "openrouter"
    assert condition_c["resident_model"] == "google/gemma-4-26b-a4b-it"
    assert condition_c["resident_billing"] == "openrouter"
    assert condition_c["sensory_calls"] == 0
    assert condition_c["boot_calls"] == 3
    assert condition_c["episode_calls"] == 3
    assert condition_c["boot_calls"] + condition_c["episode_calls"] == 6

    # the module constants agree with the frozen artifact
    assert v2.RESIDENT_ALTERNATE_PROVIDER == "openrouter"
    assert v2.RESIDENT_ALTERNATE_MODEL == "google/gemma-4-26b-a4b-it"

    # ...and that ledger is NOT the ASICloud one
    assert condition_c["resident_provider"] != v2.RESIDENT_PRIMARY_PROVIDER
    assert condition_c["resident_billing"] != "asicloud"


def test_condition_c_contributes_zero_to_the_asicloud_allocation() -> None:
    """C is executable under the existing v2 without raising the ASICloud cap."""
    frozen = json.loads(
        (ROOT / "benchmark" / "protocol-v2.json").read_text(encoding="utf-8"))
    asicloud_calls = sum(
        c["boot_calls"] + c["episode_calls"]
        for c in frozen["conditions"] if c.get("resident_billing") == "asicloud")
    condition_c = next(c for c in frozen["conditions"] if c["condition_id"] == "C")
    c_calls = condition_c["boot_calls"] + condition_c["episode_calls"]

    # A (36) + B2 (6) already fill the allocation; C adds nothing to it
    assert asicloud_calls == v2.ASICLOUD_MAX_CALLS == 42
    assert c_calls == 6
    assert asicloud_calls + 0 == v2.ASICLOUD_MAX_CALLS
    # running C does not push the ASICloud ledger past its cap
    assert asicloud_calls <= v2.ASICLOUD_MAX_CALLS


def test_asicloud_cap_was_not_raised() -> None:
    assert v2.ASICLOUD_MAX_CALLS == 42
    assert v2.ASICLOUD_MAX_INPUT_TOKENS == 124_572
    assert v2.ASICLOUD_MAX_OUTPUT_TOKENS == 21_714


# --- results, preserved literally ---------------------------------------------


def test_exact_match_results(runs, items) -> None:
    for item_id in PASSED_ITEMS:
        run = runs[item_id]
        assert run["exact_match"] is True
        assert (run["response"] or "").strip() == items[item_id]["expected_answer"]
    assert runs[FAILED_ITEM]["exact_match"] is False


def test_the_failed_run_is_preserved_literally(runs) -> None:
    """RED appears in the log as an invalid skill call. That is still a FAIL."""
    run = runs[FAILED_ITEM]
    assert run["expected_answer"] == "RED"
    assert run["response"] in (None, "")
    assert run["manifest"]["status"] == "terminated_without_response"
    assert run["manifest"]["termination_reason"] == "timeout"
    assert run["manifest"]["response_present"] is False
    assert run["exact_match"] is not True


def test_the_failed_run_had_a_fully_correct_sensory_constituent(runs, items) -> None:
    """Sensing was not the broken link in B2 either."""
    b1 = json.loads(
        (ROOT / "benchmark" / "screening-v2-B1.json").read_text(encoding="utf-8"))
    call = next(c for c in b1["calls"]
                if c["item_id"] == FAILED_ITEM and c["repeat_index"] == 0)
    scored = scorer.score_item(call["normalized_handoff"], items[FAILED_ITEM]["facts"])
    assert scored["schema_conformant"] is True
    assert scored["correct"] == scored["expected"] == 4
    assert runs[FAILED_ITEM]["handoff_payload_sha256"] == \
        a22.FROZEN_HANDOFF_SHA256[FAILED_ITEM]


# --- the paired contrast ------------------------------------------------------


def test_paired_contrast_holds_the_task_and_resident_fixed(runs, condition_a, items) -> None:
    for item_id in v2.B2_ITEMS:
        a_run, b_run = condition_a[item_id], runs[item_id]
        # same frozen instruction on both sides
        assert (a_run["manifest"]["ingress"]["text_sha256"]
                == b_run["human_text_sha256"]
                == a22.FROZEN_HUMAN_TEXT_SHA256[item_id])
        # same resident
        assert a_run["manifest"]["requested_model"] == b_run["manifest"]["requested_model"]
        assert a_run["manifest"]["upstream_provider"] == b_run["manifest"]["upstream_provider"]


def test_sensory_evidence_is_the_thing_that_differs(runs, condition_a) -> None:
    """dots handoff vs qwen handoff: different bytes, same task, same resident."""
    for item_id in v2.B2_ITEMS:
        dots = json.loads(condition_a[item_id]["payload"])["sensory_handoff"]
        dots_sha = a22.sha256_text(
            json.dumps(dots, ensure_ascii=False, sort_keys=True))
        assert dots_sha != runs[item_id]["handoff_payload_sha256"]


def test_both_handoffs_carried_every_fact_the_task_needs(runs, condition_a, items) -> None:
    """Scored with the FROZEN scorer only -- no new judge is introduced."""
    b1 = json.loads(
        (ROOT / "benchmark" / "screening-v2-B1.json").read_text(encoding="utf-8"))
    for item_id in v2.B2_ITEMS:
        facts = items[item_id]["facts"]
        dots = condition_a[item_id]["sensory_score"]
        call = next(c for c in b1["calls"]
                    if c["item_id"] == item_id and c["repeat_index"] == 0)
        qwen = scorer.score_item(call["normalized_handoff"], facts)
        assert dots["correct"] == dots["expected"] == len(facts)
        assert qwen["correct"] == qwen["expected"] == len(facts)


def test_no_pass_fail_transition_on_any_paired_item(runs, condition_a) -> None:
    """The headline paired result: swapping the sensory model changed no outcome."""
    for item_id in v2.B2_ITEMS:
        assert bool(condition_a[item_id]["exact_match"]) == bool(runs[item_id]["exact_match"])


def test_distractor_selection_failed_identically_in_both_conditions(runs, condition_a) -> None:
    """Different symbolic evidence did not change the resident's emission behaviour."""
    a_run, b_run = condition_a[FAILED_ITEM], runs[FAILED_ITEM]
    assert a_run["exact_match"] is False and b_run["exact_match"] is False
    for run in (a_run, b_run):
        assert run["manifest"]["termination_reason"] == "timeout"
        assert run["manifest"]["response_present"] is False


# --- scope --------------------------------------------------------------------


def test_condition_c_did_not_contaminate_the_b2_artifact(data, runs) -> None:
    """C has since run on OpenRouter. B2 stays an ASICloud MiniMax condition."""
    assert data["condition_id"] == "B2"
    assert data["resident_provider"] == "asicloud"
    for run in runs.values():
        assert run["manifest"]["upstream_provider"] == "ASICloud"
        assert run["manifest"]["requested_model"] == "minimax/minimax-m3"


def test_no_new_scorer_was_introduced() -> None:
    source = (SCRIPTS / "score_handoff.py").read_text(encoding="utf-8")
    assert "is located to the left of" not in source
    for token in ("b2", "amendment", "replay"):
        assert token not in source.lower().split("\n\n")[0]
