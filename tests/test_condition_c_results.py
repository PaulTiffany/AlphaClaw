"""Protocol v2 Condition C -- resident substitution, frozen results.

Offline. No network, no container, no provider call, no new scorer or judge.

C holds the resident-facing evidence byte-identical to Condition A and substitutes only
the resident model: ASICloud minimax/minimax-m3 -> OpenRouter google/gemma-4-26b-a4b-it.
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

import analyze_condition_a as analyze


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v2 = _load("protocol_v2_c", SCRIPTS / "protocol_v2.py")

ARTIFACT = ROOT / "benchmark" / "benchmark-v2-C.json"
ARTIFACT_SHA = "b46ea2ceb4429c15bd3fa5b422d4e47e5a3acdb70467b6c5a3960eee090f6c88"
A_SHA = "644f36e406df5520f54e6bcb706b891e9dd1ff9094c6c0d59cfb305e68be65ea"
B2_SHA = "8b6cc4557b27c8cc2acf7803ca05293b0fd39ca1fe1cc6f89dbe838045fd7d48"

CASES = ("number_arithmetic:text_control",
         "ocr_count:image_text",
         "number_arithmetic:image_text")

FROZEN_PAYLOAD_SHA = {
    "number_arithmetic:text_control":
        "859fee767e82eb551330202f23ea89807bd97d7c0c9091630ecb8c2c60e3101e",
    "ocr_count:image_text":
        "11a7248e67f49607b5e299ad9ead8838bebfb15cc34ce30e1660bd3df0fc812d",
    "number_arithmetic:image_text":
        "d9ce39ed6d6a57d459af5dc1604180d22ac711074210a016ee7e56513882f074",
}


@pytest.fixture(scope="module")
def data():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def runs(data):
    return {r["case_id"]: r for r in data["runs"]}


# --- frozen artifacts ---------------------------------------------------------


def test_artifact_digest_is_frozen() -> None:
    assert hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() == ARTIFACT_SHA


def test_upstream_artifacts_unchanged() -> None:
    for name, expected in (("benchmark-v2-A.json", A_SHA),
                           ("benchmark-v2-B2.json", B2_SHA)):
        assert hashlib.sha256(
            (ROOT / "benchmark" / name).read_bytes()).hexdigest() == expected


def test_three_preregistered_cases(data, runs) -> None:
    assert data["condition_id"] == "C"
    assert data["attempted_runs"] == 3
    assert set(runs) == set(CASES)
    declared = {f"{item}:{cond}" for item, cond in v2.C_CONDITIONS}
    assert set(runs) == declared


# --- the eight invariants -----------------------------------------------------


def test_every_run_passed_all_invariants_before_its_provider_call(runs) -> None:
    for case_id, run in runs.items():
        assert run["all_checks_passed"] is True, case_id
        assert run["provider_call_made"] is True
        assert all(run["checks"].values()), (case_id, run["checks"])


def test_resident_facing_payload_is_byte_identical_to_condition_a(runs) -> None:
    """The intervention invariant: only the resident changes."""
    for case_id, run in runs.items():
        assert run["resident_facing_payload_sha256"] == FROZEN_PAYLOAD_SHA[case_id]
        assert run["envelope_payload_sha256"] == FROZEN_PAYLOAD_SHA[case_id]
        assert run["envelope_matches_source"] is True
        assert run["paired_condition_a"]["payload_equal_to_c"] is True


def test_zero_sensory_calls(data, runs) -> None:
    assert data["sensory_calls"] == 0
    for run in runs.values():
        ingress = run["manifest"]["ingress"]
        assert ingress["route"] == "text_passthrough"
        assert ingress["sensory_inference"] is False
        assert "sensory_trace" not in ingress
        assert run["provenance"]["sensory_inference"] is False


def test_zero_asicloud_calls(data, runs) -> None:
    assert data["asicloud_calls"] == 0
    for run in runs.values():
        assert run["manifest"]["upstream_provider"] == "OpenRouter"
        for receipt in run["provider_usage"]:
            assert receipt["provider"] == "OpenRouter"
            assert receipt["provider"].lower() != "asicloud"


def test_provenance_is_explicit_and_truthful(runs) -> None:
    for case_id, run in runs.items():
        provenance = run["provenance"]
        assert provenance["replayed_from"] == "A"
        assert provenance["source_condition"] == case_id
        assert provenance["origin_run_id"]
        assert provenance["resident_facing_payload_sha256"] == FROZEN_PAYLOAD_SHA[case_id]
        # a text control genuinely IS native text; a handoff replay is not
        expected_native = case_id.endswith(":text_control")
        assert provenance["is_native_text_condition"] is expected_native


# --- no fallback or substitution ----------------------------------------------


def test_requested_and_resolved_model_are_the_preregistered_one(runs) -> None:
    for case_id, run in runs.items():
        assert run["manifest"]["requested_model"] == v2.RESIDENT_ALTERNATE_MODEL
        assert run["manifest"]["requested_model"] == "google/gemma-4-26b-a4b-it"
        for receipt in run["provider_usage"]:
            assert receipt["model"] == "google/gemma-4-26b-a4b-it", case_id


def test_no_fallback_model_appears_anywhere(data) -> None:
    blob = json.dumps(data)
    for forbidden in ("z-ai/glm-5.2", "openrouter/free", "minimax/minimax-m3:",
                      "qwen/qwen3.7-flash"):
        assert forbidden not in blob, forbidden


def test_exactly_three_boot_and_three_episode_openrouter_calls(runs) -> None:
    boot = episode = 0
    for case_id, run in runs.items():
        usage = run["manifest"]["usage_by_phase"]
        assert usage["boot"]["calls"] == 1, case_id
        assert usage["episode"]["calls"] == 1, case_id
        boot += usage["boot"]["calls"]
        episode += usage["episode"]["calls"]
    assert (boot, episode) == (3, 3)
    assert boot + episode == 6


# --- results, preserved literally ---------------------------------------------


def test_no_case_matched(runs) -> None:
    for case_id, run in runs.items():
        assert run["exact_match"] is False, case_id


def test_responses_are_preserved_verbatim(runs) -> None:
    assert runs["number_arithmetic:text_control"]["response"] == \
        "processing benchmark ingress evidence\n"
    assert runs["ocr_count:image_text"]["response"] == "waiting for analysis...\n"
    assert runs["number_arithmetic:image_text"]["response"] in (None, "")


def test_failure_decomposition_uses_the_frozen_classifier(data, runs) -> None:
    """Same derived semantics as Condition A; no new judge."""
    assert data["failure_decomposition"] == {
        "sensory": 0, "reasoning_composition": 2, "output_contract": 1,
        "infrastructure": 0, "provider_availability": 0, "passed": 0,
    }
    for case_id, run in runs.items():
        assert analyze.classify(run) == run["failure_class"], case_id


def test_the_timed_out_case_is_output_contract_not_rounded_up(runs) -> None:
    """Gemma derived 19 and emitted it as an invalid skill call. Still a FAIL."""
    run = runs["number_arithmetic:image_text"]
    assert run["manifest"]["status"] == "terminated_without_response"
    assert run["manifest"]["termination_reason"] == "timeout"
    assert run["manifest"]["response_present"] is False
    assert run["failure_class"] == analyze.OUTPUT_CONTRACT
    assert run["exact_match"] is False


# --- the paired contrast ------------------------------------------------------


def test_paired_runs_differ_only_in_the_resident(runs) -> None:
    for run in runs.values():
        paired = run["paired_condition_a"]
        assert paired["payload_equal_to_c"] is True
        assert paired["resident_provider"] == "ASICloud"
        assert paired["resident_model"] == "minimax/minimax-m3"
        assert run["manifest"]["upstream_provider"] == "OpenRouter"
        assert run["manifest"]["requested_model"] == "google/gemma-4-26b-a4b-it"


def test_all_three_paired_cases_transitioned_pass_to_fail(runs) -> None:
    """The headline result on these three preregistered cases only."""
    for case_id, run in runs.items():
        paired = run["paired_condition_a"]
        assert paired["exact_match"] is True, case_id
        assert run["exact_match"] is False, case_id
        assert paired["transition"] == "PASS -> FAIL"


def test_condition_a_and_b2_artifacts_were_not_touched_by_condition_c() -> None:
    a = json.loads((ROOT / "benchmark" / "benchmark-v2-A.json").read_text(encoding="utf-8"))
    b2 = json.loads((ROOT / "benchmark" / "benchmark-v2-B2.json").read_text(encoding="utf-8"))
    assert a["condition_id"] == "A"
    assert b2["condition_id"] == "B2"
    assert all(r["manifest"]["upstream_provider"] == "ASICloud" for r in b2["runs"])
