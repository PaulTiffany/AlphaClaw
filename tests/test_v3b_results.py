"""Protocol v3-B results -- frozen receipts and derived economics.

Offline. No network, no container, no provider call, no judge.

Every headline figure asserted here is recomputed from the raw receipts by
``scripts/analyze_v3b.py``; none is a hand-typed statistic.
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

import analyze_v3b as analyze
import economics_v3


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


p3 = _load("protocol_v3_b_results", SCRIPTS / "protocol_v3.py")

ARTIFACT = ROOT / "benchmark" / "benchmark-v3-B.json"
ARTIFACT_SHA = "f5ddcf3d77f010a4d199d6eea4c87fa093b3fe7576d01258a9997b9b493aeab2"
MANIFEST_SHA = "a725e3e8413b7da00eebe5a334347e2a9627ab1d5e9f7173b6b5007c1b5a7757"

UPSTREAM_DIGESTS = {
    "protocol-v2.json": "b5ee0c3760a9540119526f1c51ac1dc5cc0d6fadc0fe1e378ddf770d3d02557f",
    "screening-v2-B1.json": "847828d469d60269a289f5183d07a69c6afc4c123ef1ad51346490e778e0ab14",
    "benchmark-v2-A.json": "644f36e406df5520f54e6bcb706b891e9dd1ff9094c6c0d59cfb305e68be65ea",
    "benchmark-v2-B2.json": "8b6cc4557b27c8cc2acf7803ca05293b0fd39ca1fe1cc6f89dbe838045fd7d48",
    "benchmark-v2-C.json": "b46ea2ceb4429c15bd3fa5b422d4e47e5a3acdb70467b6c5a3960eee090f6c88",
    "benchmark-v3-A.json": "98ab018e8f8dcb2de405e21a800239583968c7832b1a8665cd31686072ad6552",
    "protocol-v3.json": "a65cbaad7640c3c64a03903dddef8b9162f08bd1d3a524fadc3367148ede0409",
    "v3b-ground-truth.json": "35ce510b03473c58a166c6fabafa93a21f6a57e16dd203a7adf7b2b64c8ef767",
}

AVAILABILITY_FAILURES = {(2, "E3_text_oracle", "chain_a", 1),
                         (3, "E1_multimodal_resident", "chain_a", 2),
                         (4, "E2_alphaclaw", "chain_a", 2),
                         (5, "E3_text_oracle", "chain_a", 2)}


@pytest.fixture(scope="module")
def data():
    return analyze.load()


# --- frozen evidence ----------------------------------------------------------


def test_artifact_digest_is_frozen() -> None:
    assert hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() == ARTIFACT_SHA


def test_execution_manifest_was_hashed_before_the_run(data) -> None:
    assert data["execution_manifest_sha256"] == MANIFEST_SHA
    manifest = data["execution_manifest"]
    recomputed = hashlib.sha256(
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ).hexdigest()
    assert recomputed == MANIFEST_SHA


def test_manifest_pins_the_frozen_population(data) -> None:
    manifest = data["execution_manifest"]
    assert manifest["ground_truth_file_sha256"] == \
        UPSTREAM_DIGESTS["v3b-ground-truth.json"]
    assert data["ground_truth_file_sha256"] == UPSTREAM_DIGESTS["v3b-ground-truth.json"]
    assert manifest["items"] == 2
    assert manifest["depths"] == [1, 2, 4, 8]
    assert manifest["repeats"] == 1
    assert len(manifest["episodes"]) == 24


def test_manifest_implies_the_preregistered_call_totals(data) -> None:
    manifest = data["execution_manifest"]
    assert manifest["planned_multimodal_calls"] == 38 == p3.V3B_MULTIMODAL_MAX_CALLS
    assert manifest["planned_text_calls"] == 60 == p3.V3B_TEXT_MAX_CALLS
    assert manifest["planned_total_calls"] == 98 == p3.V3B_MAX_CALLS


def test_all_upstream_artifacts_unchanged() -> None:
    for name, expected in UPSTREAM_DIGESTS.items():
        actual = hashlib.sha256(
            (ROOT / "benchmark" / name).read_bytes()).hexdigest()
        assert actual == expected, name
    for item, digest in (("chain_a", "16454976d4be08df49380dd26a9e611a890d71ddc0f2a3c405da28672e6ed54c"),
                         ("chain_b", "758ab03f2d7238de860d03749094f1e284c2c0ec59af54c09a2aa41c6b00919a")):
        path = ROOT / "benchmark" / "v3b-stimuli" / f"{item}.png"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


# --- population and matrix ----------------------------------------------------


def test_all_twenty_four_episodes_attempted(data) -> None:
    assert data["attempted_episodes"] == 24
    assert len(data["episodes"]) == 24
    assert data["stopped_early"] is None
    keys = {(e["architecture"], e["item_id"], e["depth"]) for e in data["episodes"]}
    assert len(keys) == 24


def test_exact_population(data) -> None:
    assert {e["item_id"] for e in data["episodes"]} == {"chain_a", "chain_b"}
    assert {e["depth"] for e in data["episodes"]} == {1, 2, 4, 8}
    assert {e["architecture"] for e in data["episodes"]} == set(
        economics_v3.ARCHITECTURES)


def test_no_retries(data) -> None:
    """One record per (arm, item, depth); no episode repeated after a failure."""
    keys = [(e["architecture"], e["item_id"], e["depth"]) for e in data["episodes"]]
    assert len(keys) == len(set(keys))
    for episode in data["episodes"]:
        steps = [c["step"] for c in episode["calls"] if analyze.is_reasoning(c)]
        assert steps == sorted(set(steps))


# --- model and provider -------------------------------------------------------


def test_exact_model_and_provider_no_substitution(data) -> None:
    receipts = analyze.model_receipts(data)
    assert receipts["requested"] == ["qwen/qwen3.7-flash"]
    assert receipts["resolved"] == ["qwen/qwen3.7-flash"]
    assert data["provider"] == "openrouter"
    assert data["requested_model"] == "qwen/qwen3.7-flash"


def test_no_fallback_model_appears(data) -> None:
    blob = json.dumps(data)
    for forbidden in ("openrouter/free", "z-ai/glm-5.2", "minimax/minimax-m3",
                      "google/gemma-4-26b-a4b-it", "dots-studio"):
        assert forbidden not in blob, forbidden


# --- arm structure, from receipts ---------------------------------------------


def test_e1_carries_the_image_on_every_reasoning_call(data) -> None:
    for episode in data["episodes"]:
        if episode["architecture"] != analyze.E1:
            continue
        reasoning = [c for c in episode["calls"] if analyze.is_reasoning(c)]
        assert reasoning
        assert all(c["carries_image"] for c in reasoning)
        assert analyze.observed_calls(episode)["perception_calls"] == 0


def test_e2_makes_exactly_one_perception_per_episode(data) -> None:
    for row in analyze.e2_fidelity(data):
        assert row["perception_calls"] == 1, (row["item_id"], row["depth"])


def test_e2_never_carries_an_image_after_perception(data) -> None:
    for row in analyze.e2_fidelity(data):
        assert row["any_reasoning_call_carried_image"] is False


def test_e2_reuses_one_identical_handoff_within_each_episode(data) -> None:
    for row in analyze.e2_fidelity(data):
        assert row["same_handoff_reused"] is True
        assert row["handoff_matches_reasoning_evidence"] is True
        if row["reasoning_calls"]:
            assert row["distinct_evidence_digests"] == 1


def test_e3_makes_zero_multimodal_calls(data) -> None:
    for episode in data["episodes"]:
        if episode["architecture"] != analyze.E3:
            continue
        counts = analyze.observed_calls(episode)
        assert counts["multimodal_calls"] == 0
        assert counts["perception_calls"] == 0
        assert all(not c["carries_image"] for c in episode["calls"])


def test_observed_call_totals(data) -> None:
    totals = analyze.call_totals(data)
    assert totals["multimodal_calls"] == 37
    assert totals["text_calls"] == 57
    assert totals["total_calls"] == 94
    by_arm = totals["by_arm"]
    assert by_arm[analyze.E1]["multimodal_calls"] == 29
    assert by_arm[analyze.E1]["text_calls"] == 0
    assert by_arm[analyze.E2]["multimodal_calls"] == 8
    assert by_arm[analyze.E2]["perception_calls"] == 8
    assert by_arm[analyze.E2]["text_calls"] == 28
    assert by_arm[analyze.E3]["multimodal_calls"] == 0
    assert by_arm[analyze.E3]["text_calls"] == 29


def test_executed_calls_are_planned_minus_calls_lost_to_failures(data) -> None:
    """94 executed = 98 planned - 4 not issued because an episode aborted."""
    lost = sum((e["multimodal_calls"] + e["text_calls"]) - len(e["calls"])
               for e in data["episodes"])
    assert lost == 4
    assert 98 - lost == analyze.call_totals(data)["total_calls"] == 94


def test_within_the_frozen_caps(data) -> None:
    totals = analyze.call_totals(data)
    assert totals["multimodal_calls"] <= p3.V3B_MULTIMODAL_MAX_CALLS
    assert totals["text_calls"] <= p3.V3B_TEXT_MAX_CALLS
    assert analyze.totals(data)["measured_cost_usd"] <= p3.V3B_MAX_COST_USD


# --- A. architecture-invariant call reduction ---------------------------------


def test_receipts_match_the_preregistered_multimodal_structure(data) -> None:
    rows = {r["depth"]: r for r in analyze.multimodal_avoidance(data)}
    for depth, avoided, fraction in ((1, 0, 0.0), (2, 1, 0.5), (4, 3, 0.75), (8, 7, 0.875)):
        row = rows[depth]
        assert row["expected_avoided"] == avoided
        assert row["expected_avoidance_fraction"] == pytest.approx(fraction)
        assert row["receipts_match_expectation"] is True, depth
        assert row["comparable_item_pairs"] >= 1
        assert all(x == avoided for x in row["observed_avoided"]), depth


def test_depth_two_has_only_one_comparable_pair(data) -> None:
    """chain_a N=2 was lost to an availability failure; it is not averaged away."""
    rows = {r["depth"]: r for r in analyze.multimodal_avoidance(data)}
    assert rows[2]["comparable_item_pairs"] == 1
    assert rows[1]["comparable_item_pairs"] == 2
    assert rows[4]["comparable_item_pairs"] == 2
    assert rows[8]["comparable_item_pairs"] == 2


# --- scoring ------------------------------------------------------------------


def test_exact_match_against_the_frozen_answers(data) -> None:
    truth = analyze.ground_truth()
    expected = {(item["item_id"], ep["depth"]): ep["expected_answer"]
                for item in truth["items"] for ep in item["episodes"]}
    assert expected[("chain_a", 8)] == "64"
    assert expected[("chain_b", 8)] == "85"
    for episode in data["episodes"]:
        key = (episode["item_id"], episode["depth"])
        assert episode["expected_answer"] == expected[key]
        if episode["terminated"] == "completed":
            assert episode["exact_match"] == (
                (episode["final_response"] or "").strip() == expected[key])


def test_success_counts(data) -> None:
    rows = analyze.success_by_arm_depth(data)
    assert sum(r["successful"] for r in rows) == 20
    assert sum(r["availability_failures"] for r in rows) == 4
    assert sum(r["incorrect"] for r in rows) == 0
    assert sum(r["attempted"] for r in rows) == 24


def test_failures_are_availability_not_wrong_answers(data) -> None:
    failed = {(e["episode_index"], e["architecture"], e["item_id"], e["depth"])
              for e in data["episodes"] if analyze.outcome(e) != "success"}
    assert failed == AVAILABILITY_FAILURES
    for episode in data["episodes"]:
        if analyze.outcome(episode) == analyze.AVAILABILITY:
            errors = " ".join(str(c.get("error") or "") for c in episode["calls"])
            assert "429" in errors


# --- B. measured cost ---------------------------------------------------------


def test_every_completed_call_has_a_receipt_cost(data) -> None:
    block = analyze.totals(data)
    assert block["calls_without_receipt_cost"] == 0
    assert block["cost_provenance"] == economics_v3.MEASURED
    assert block["estimated_values_reported"] is False


def test_measured_totals_reconstruct_from_receipts(data) -> None:
    block = analyze.totals(data)
    assert block["measured_cost_usd"] == pytest.approx(0.00671068, abs=1e-8)
    assert block["input_tokens"] == 11_772
    assert block["output_tokens"] == 48_904
    recomputed = sum(c["cost"] for e in data["episodes"] for c in e["calls"]
                     if c.get("cost_available"))
    assert recomputed == pytest.approx(block["measured_cost_usd"], abs=1e-8)


def test_e1_vs_e2_measured_savings_by_depth(data) -> None:
    rows = {r["depth"]: r for r in analyze.e1_vs_e2_savings(data)}
    assert rows[1]["alphaclaw_cheaper"] is False        # amortisation has not begun
    for depth in (2, 4, 8):
        assert rows[depth]["alphaclaw_cheaper"] is True, depth
    assert rows[1]["measured_savings_usd"] < 0
    assert all(rows[d]["cost_provenance"] == economics_v3.MEASURED for d in rows)


def test_shallow_depth_loss_is_not_hidden(data) -> None:
    rows = {r["depth"]: r for r in analyze.e1_vs_e2_savings(data)}
    assert rows[1]["measured_savings_fraction"] < 0


def test_break_even_is_observed_not_interpolated(data) -> None:
    block = analyze.break_even(data)
    assert block["depths_where_alphaclaw_dearer"] == [1]
    assert block["depths_where_alphaclaw_cheaper"] == [2, 4, 8]
    assert block["observed_sign_change"] is True
    assert block["interpolated_break_even_point"] is None
    assert "No break-even point is interpolated" in block["note"]


# --- C. success-adjusted utility ----------------------------------------------


def test_cost_per_success_exposes_its_denominator(data) -> None:
    for row in analyze.cost_by_arm_depth(data):
        if row["successful_episodes"]:
            assert row["cost_per_successful_episode"] == pytest.approx(
                row["measured_cost_usd"] / row["successful_episodes"])
            assert row["defined"] is True
        else:
            assert row["cost_per_successful_episode"] is None
            assert row["defined"] is False


def test_alphaclaw_beats_the_baseline_on_cost_per_success_at_depth_four_and_eight(
        data) -> None:
    rows = {(r["architecture"], r["depth"]): r for r in analyze.cost_by_arm_depth(data)}
    for depth in (4, 8):
        e1 = rows[(analyze.E1, depth)]
        e2 = rows[(analyze.E2, depth)]
        assert e1["successful_episodes"] == e2["successful_episodes"] == 2
        assert e2["cost_per_successful_episode"] < e1["cost_per_successful_episode"]


def test_a_cheaper_failing_arm_can_never_win(data) -> None:
    failing = {**economics_v3.cost_per_successful_episode(
        total_cost=0.000001, successful_episodes=0,
        provenance=economics_v3.MEASURED), "label": "cheap_failer"}
    real = {(r["architecture"], r["depth"]): r for r in analyze.cost_by_arm_depth(data)}
    working = {**real[(analyze.E2, 8)], "label": "E2"}
    assert economics_v3.economically_superior(failing, working) is None


def test_the_three_results_are_not_collapsed() -> None:
    source = (SCRIPTS / "analyze_v3b.py").read_text(encoding="utf-8")
    assert "economic score" not in source.lower().replace('"economic score"', "")
    for section in ("architecture-invariant call reduction",
                    "measured current-price", "success-adjusted utility"):
        assert section in source


# --- caveats retained ---------------------------------------------------------


def test_depth_one_caveat_retained_in_the_frozen_population() -> None:
    truth = analyze.ground_truth()
    note = truth["depth_1_property"]
    assert "degenerate ACCURACY comparison" in note
    assert "no-amortisation economic baseline" in note


def test_analysis_module_makes_no_provider_call() -> None:
    import ast

    banned = {"requests", "urllib", "socket", "http", "httpx", "subprocess", "docker"}
    tree = ast.parse((SCRIPTS / "analyze_v3b.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not (imported & banned)


def test_v3a_untouched() -> None:
    assert hashlib.sha256(
        (ROOT / "benchmark" / "benchmark-v3-A.json").read_bytes()).hexdigest() == \
        UPSTREAM_DIGESTS["benchmark-v3-A.json"]
