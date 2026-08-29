"""Protocol v3-B population freeze -- offline fixture and arm tests.

No network, no container, no provider call. These tests exist to establish one property
before any model sees anything: **the benchmark population is fixed**.

They regenerate the stimuli and ground truth independently and prove byte equality with
the committed fixtures, so execution must consume the frozen bytes rather than sample
new examples at run time.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import arms_v3b
import economics_v3
import make_benchmark_suite
import make_v3b_suite as v3b
import protocol_v3

STIMULI = ROOT / "benchmark" / "v3b-stimuli"
GROUND_TRUTH = ROOT / "benchmark" / "v3b-ground-truth.json"

GROUND_TRUTH_FILE_SHA = "35ce510b03473c58a166c6fabafa93a21f6a57e16dd203a7adf7b2b64c8ef767"
GROUND_TRUTH_DOC_SHA = "a2b1c2747f5c8d5ad226be27ce7e8d269838d54d622832ac6787d76b246c9b21"
IMAGE_SHA = {
    "chain_a": "16454976d4be08df49380dd26a9e611a890d71ddc0f2a3c405da28672e6ed54c",
    "chain_b": "758ab03f2d7238de860d03749094f1e284c2c0ec59af54c09a2aa41c6b00919a",
}
EXPECTED_ANSWERS = {
    ("chain_a", 1): "7", ("chain_a", 2): "19", ("chain_a", 4): "33", ("chain_a", 8): "64",
    ("chain_b", 1): "9", ("chain_b", 2): "21", ("chain_b", 4): "40", ("chain_b", 8): "85",
}

V2_DIGESTS = {
    "protocol-v2.json": "b5ee0c3760a9540119526f1c51ac1dc5cc0d6fadc0fe1e378ddf770d3d02557f",
    "screening-v2-B1.json": "847828d469d60269a289f5183d07a69c6afc4c123ef1ad51346490e778e0ab14",
    "benchmark-v2-A.json": "644f36e406df5520f54e6bcb706b891e9dd1ff9094c6c0d59cfb305e68be65ea",
    "benchmark-v2-B2.json": "8b6cc4557b27c8cc2acf7803ca05293b0fd39ca1fe1cc6f89dbe838045fd7d48",
    "benchmark-v2-C.json": "b46ea2ceb4429c15bd3fa5b422d4e47e5a3acdb70467b6c5a3960eee090f6c88",
    "benchmark-v3-A.json": "98ab018e8f8dcb2de405e21a800239583968c7832b1a8665cd31686072ad6552",
}


@pytest.fixture(scope="module")
def committed():
    return json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def regenerated():
    """Rebuild from the committed parameters, without writing anything."""
    return v3b.build_suite()


# --- the population is frozen -------------------------------------------------


def test_committed_ground_truth_file_digest() -> None:
    assert hashlib.sha256(GROUND_TRUTH.read_bytes()).hexdigest() == GROUND_TRUTH_FILE_SHA


def test_regeneration_reproduces_the_committed_ground_truth(committed, regenerated) -> None:
    """Independent regeneration must equal the committed bytes exactly."""
    assert regenerated == committed
    assert regenerated["ground_truth_sha256"] == GROUND_TRUTH_DOC_SHA


def test_regeneration_reproduces_the_committed_images(regenerated) -> None:
    for spec in v3b.ITEMS:
        rendered = v3b.render_item(spec)
        on_disk = (STIMULI / f"{spec['item_id']}.png").read_bytes()
        assert rendered == on_disk, spec["item_id"]
        assert hashlib.sha256(rendered).hexdigest() == IMAGE_SHA[spec["item_id"]]


def test_generator_is_deterministic() -> None:
    assert v3b.build_suite() == v3b.build_suite()
    for spec in v3b.ITEMS:
        assert v3b.render_item(spec) == v3b.render_item(spec)


def test_population_is_complete_and_exactly_as_preregistered(committed) -> None:
    assert committed["family"] == "chained_accumulation"
    assert committed["repeats"] == 1 == protocol_v3.V3B_REPEATS
    assert len(committed["items"]) == 2 == protocol_v3.V3B_ITEMS
    assert committed["depths"] == [1, 2, 4, 8] == list(protocol_v3.V3B_DEPTHS)
    for item in committed["items"]:
        assert len(item["integers"]) == 8
        assert [e["depth"] for e in item["episodes"]] == [1, 2, 4, 8]


def test_every_committed_image_exists_and_matches_its_recorded_digest(committed) -> None:
    for item in committed["items"]:
        path = STIMULI / item["image_filename"]
        assert path.exists(), item["item_id"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["image_sha256"]


# --- ground truth -------------------------------------------------------------


def test_expected_answers_are_mechanically_derivable(committed) -> None:
    for item in committed["items"]:
        integers = item["integers"]
        for episode in item["episodes"]:
            depth = episode["depth"]
            assert episode["expected_answer"] == str(sum(integers[:depth]))
            assert episode["expected_answer"] == \
                EXPECTED_ANSWERS[(item["item_id"], depth)]


def test_reasoning_chain_is_complete_and_consistent(committed) -> None:
    for item in committed["items"]:
        integers = item["integers"]
        for episode in item["episodes"]:
            chain = episode["chain"]
            assert len(chain) == episode["depth"] == episode["reasoning_steps"]
            running = 0
            for step in chain:
                running += step["addend"]
                assert step["running_total"] == running
                assert step["addend"] == integers[step["step"] - 1]
            assert str(running) == episode["expected_answer"]


def test_initial_state_and_output_contract_are_recorded(committed) -> None:
    for item in committed["items"]:
        assert item["initial_state"] == 0
        assert item["output_contract"] == \
            "Use digits only. Reply with no spaces and no other text."


def test_scored_totals_never_collide_with_a_displayed_integer(committed) -> None:
    """Otherwise a wrong answer could be indistinguishable from a misread digit."""
    for item in committed["items"]:
        displayed = set(item["integers"])
        for episode in item["episodes"]:
            if episode["depth"] == 1:
                continue      # at depth 1 the answer IS the first integer, by design
            assert int(episode["expected_answer"]) not in displayed


def test_every_displayed_integer_is_renderable(committed) -> None:
    for item in committed["items"]:
        for value in item["integers"]:
            assert set(str(value)) <= v3b.RENDERABLE_DIGITS, value


# --- leakage ------------------------------------------------------------------


def test_no_answer_leakage_beyond_the_inherent_depth_one_case(regenerated) -> None:
    rows = arms_v3b.leakage_report(regenerated)
    assert rows
    leaked = [r for r in rows if r["answer_leaked"]]
    assert leaked == []


def test_depth_one_answer_presence_is_declared_not_hidden(regenerated, committed) -> None:
    rows = arms_v3b.leakage_report(regenerated)
    inherent = [r for r in rows if r["inherent_at_depth_1"]]
    assert len(inherent) == 4          # E2 and E3, two items
    assert all(r["answer_present_in_prompts"] for r in inherent)
    assert all(r["architecture"] != arms_v3b.E1 for r in inherent)
    note = committed["depth_1_property"]
    assert "degenerate ACCURACY comparison" in note
    assert "recorded rather than engineered away" in note


def test_no_reasoning_chain_leakage(regenerated) -> None:
    rows = arms_v3b.leakage_report(regenerated)
    assert [r for r in rows if r["full_chain_leaked"]] == []


def test_a_step_prompt_carries_only_the_state_handed_in(committed) -> None:
    for item in committed["items"]:
        integers = item["integers"]
        for episode in item["episodes"]:
            for index, prompt in enumerate(episode["step_prompts"], start=1):
                previous = sum(integers[: index - 1])
                assert str(previous) in prompt
                answer_here = sum(integers[:index])
                if answer_here != previous:
                    assert not re.search(rf"(?<![0-9]){answer_here}(?![0-9])", prompt)


# --- the three arms -----------------------------------------------------------


def test_reasoning_step_parity_across_arms(regenerated) -> None:
    """Amendment v3.2's central invariant."""
    for item in regenerated["items"]:
        for depth in regenerated["depths"]:
            for architecture in economics_v3.ARCHITECTURES:
                built = arms_v3b.episode(architecture, item["item_id"], depth, regenerated)
                assert built["reasoning_steps"] == depth, (architecture, depth)
                assert economics_v3.reasoning_steps(architecture, depth) == depth


def test_e2_pays_exactly_one_perception_call(regenerated) -> None:
    for item in regenerated["items"]:
        for depth in regenerated["depths"]:
            e2 = arms_v3b.episode(arms_v3b.E2, item["item_id"], depth, regenerated)
            assert e2["perception_calls"] == 1
            assert e2["multimodal_calls"] == 1
            assert e2["text_calls"] == depth
            assert e2["total_provider_calls"] == depth + 1
            assert economics_v3.perception_calls(arms_v3b.E2, depth) == 1


def test_e1_carries_the_image_on_every_reasoning_call(regenerated) -> None:
    for item in regenerated["items"]:
        for depth in regenerated["depths"]:
            e1 = arms_v3b.episode(arms_v3b.E1, item["item_id"], depth, regenerated)
            assert e1["multimodal_calls"] == depth
            assert e1["text_calls"] == 0
            assert all(call["carries_image"] for call in e1["calls"])


def test_e2_reasoning_calls_contain_no_image(regenerated) -> None:
    """E2 must never re-perceive: that is the architecture under test."""
    for item in regenerated["items"]:
        for depth in regenerated["depths"]:
            calls = arms_v3b.reasoning_calls(arms_v3b.E2, item["item_id"], depth,
                                             regenerated)
            assert all(call["carries_image"] is False for call in calls)
            assert all(call["image_filename"] is None for call in calls)
            assert all(call["evidence_text"] for call in calls)


def test_e3_contains_no_image_and_no_multimodal_call(regenerated) -> None:
    for item in regenerated["items"]:
        for depth in regenerated["depths"]:
            e3 = arms_v3b.episode(arms_v3b.E3, item["item_id"], depth, regenerated)
            assert e3["multimodal_calls"] == 0
            assert all(call["carries_image"] is False for call in e3["calls"])


def test_oracle_facts_equal_the_visual_ground_truth_exactly(regenerated) -> None:
    """E3's oracle states exactly the displayed integers -- no totals, no chain."""
    for item in regenerated["items"]:
        facts = item["oracle_facts"]
        assert facts == v3b.oracle_facts(tuple(item["integers"]))
        listed = [int(x) for x in re.findall(r"\d+", facts)]
        assert listed == item["integers"]


def test_all_three_arms_use_the_same_task_and_instruction(regenerated) -> None:
    for item in regenerated["items"]:
        for depth in regenerated["depths"]:
            builts = [arms_v3b.episode(a, item["item_id"], depth, regenerated)
                      for a in economics_v3.ARCHITECTURES]
            assert len({b["expected_answer"] for b in builts}) == 1
            assert len({b["output_contract"] for b in builts}) == 1
            instructions = [
                tuple(c["instruction"] for c in b["calls"] if c["kind"] == "reasoning")
                for b in builts]
            assert len(set(instructions)) == 1


def test_e2_and_e3_evidence_carry_the_same_underlying_facts(regenerated) -> None:
    for item in regenerated["items"]:
        handoff_numbers = item["symbolic_handoff"]["observation"]["numbers_left_to_right"]
        oracle_numbers = [int(x) for x in re.findall(r"\d+", item["oracle_facts"])]
        assert handoff_numbers == oracle_numbers == item["integers"]


# --- the call matrix ----------------------------------------------------------


def test_call_matrix_regenerates_the_preregistered_totals(regenerated) -> None:
    """Derived from the actual fixtures, not asserted against a hardcoded agreement."""
    matrix = arms_v3b.call_matrix(regenerated)
    assert matrix["multimodal_calls"] == 38
    assert matrix["text_calls"] == 60
    assert matrix["total_calls"] == 98
    assert len(matrix["episodes"]) == 2 * 4 * 3

    frozen = protocol_v3.v3b_call_budget()
    assert matrix["multimodal_calls"] == frozen["multimodal_calls"]
    assert matrix["text_calls"] == frozen["text_calls"]
    assert matrix["total_calls"] == frozen["total_calls"]


def test_matrix_totals_are_a_sum_of_per_episode_counts(regenerated) -> None:
    matrix = arms_v3b.call_matrix(regenerated)
    assert sum(e["multimodal_calls"] for e in matrix["episodes"]) == 38
    assert sum(e["text_calls"] for e in matrix["episodes"]) == 60


def test_budget_caps_unchanged() -> None:
    assert protocol_v3.V3B_MULTIMODAL_MAX_CALLS == 38
    assert protocol_v3.V3B_TEXT_MAX_CALLS == 60
    assert protocol_v3.V3B_MAX_CALLS == 98
    assert protocol_v3.V3B_MAX_COST_USD == 2.00
    assert protocol_v3.V3_MAX_COST_USD == 2.50


# --- Amendment v3.2 economics -------------------------------------------------


def test_amended_cost_equation_is_in_force() -> None:
    assert economics_v3.AMENDMENT_VERSION == "v3.2"
    c_mm, c_text = 0.010, 0.001
    for depth in (1, 2, 4, 8):
        assert economics_v3.cost_alphaclaw(depth, c_mm, c_text) ==             pytest.approx(c_mm + depth * c_text)


def test_superseded_formula_is_not_used_as_the_comparison() -> None:
    c_mm, c_text = 0.010, 0.001
    for depth in (2, 4, 8):
        superseded = c_mm + (depth - 1) * c_text
        assert economics_v3.cost_alphaclaw(depth, c_mm, c_text) !=             pytest.approx(superseded)
    source = (SCRIPTS / "economics_v3.py").read_text(encoding="utf-8")
    assert "(depth - 1) * c_text" not in source


def test_negative_savings_at_depth_one_is_preserved() -> None:
    c_mm, c_text = 0.010, 0.001
    assert economics_v3.savings(1, c_mm, c_text) < 0
    assert economics_v3.savings_fraction(1, c_mm, c_text) < 0
    assert economics_v3.savings(2, c_mm, c_text) > 0


def test_multimodal_avoidance_metric_is_unchanged_and_scoped() -> None:
    for depth, avoided, fraction in ((1, 0, 0.0), (2, 1, 0.5), (4, 3, 0.75), (8, 7, 0.875)):
        structure = economics_v3.expected_call_structure(depth)
        assert structure["multimodal_calls_avoided"] == avoided
        assert structure["multimodal_avoidance_fraction"] == pytest.approx(fraction)
        assert structure["reasoning_steps_per_arm"] == depth
        assert structure["e2_total_provider_calls"] == depth + 1
        assert "NOT total provider-call" in structure["metric_scope"]


def test_measured_and_estimated_labels_stay_distinct() -> None:
    measured = economics_v3.cost_per_successful_episode(
        total_cost=0.01, successful_episodes=2, provenance=economics_v3.MEASURED)
    estimated = economics_v3.cost_per_successful_episode(
        total_cost=0.01, successful_episodes=2, provenance=economics_v3.ESTIMATED)
    assert measured["cost_provenance"] == "measured"
    assert estimated["cost_provenance"] == "estimated"
    with pytest.raises(economics_v3.EconomicsError):
        economics_v3.cost_per_successful_episode(
            total_cost=0.01, successful_episodes=1, provenance="catalog")


def test_success_adjusted_economics_cannot_reward_failure() -> None:
    failing = {**economics_v3.cost_per_successful_episode(
        total_cost=0.0001, successful_episodes=0,
        provenance=economics_v3.MEASURED), "label": "cheap_failer"}
    working = {**economics_v3.cost_per_successful_episode(
        total_cost=0.05, successful_episodes=4,
        provenance=economics_v3.MEASURED), "label": "works"}
    assert failing["cost_per_successful_episode"] is None
    assert failing["defined"] is False
    assert economics_v3.economically_superior(failing, working) is None


# --- nothing else moved -------------------------------------------------------


def test_v2_and_v3a_artifacts_unchanged() -> None:
    for name, expected in V2_DIGESTS.items():
        actual = hashlib.sha256(
            (ROOT / "benchmark" / name).read_bytes()).hexdigest()
        assert actual == expected, name


def test_v2_stimulus_generator_and_items_untouched() -> None:
    """The v3-B generator is a NEW module; v2 items must render identically."""
    document = make_benchmark_suite.build_suite()
    frozen = json.loads((ROOT / "benchmark" / "items.json").read_text(encoding="utf-8"))
    by_id = {item["item_id"]: item for item in frozen["items"]}
    for item in document["items"]:
        assert item["image_sha256"] == by_id[item["item_id"]]["image_sha256"]


def test_v3b_generator_does_not_modify_the_v2_generator() -> None:
    source = (SCRIPTS / "make_v3b_suite.py").read_text(encoding="utf-8")
    assert "make_benchmark_suite" not in source     # imports the primitives module only
    assert "from make_benchmark_stimuli import" in source


def test_no_provider_or_network_path_in_any_v3b_module() -> None:
    """Structural, not textual: parse the imports rather than grep the prose."""
    import ast

    banned = {"requests", "urllib", "socket", "http", "httpx", "subprocess",
              "docker", "openrouter_image", "ssl", "asyncio"}
    for name in ("make_v3b_suite.py", "arms_v3b.py", "economics_v3.py"):
        source = (SCRIPTS / name).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not (imported & banned), (name, sorted(imported & banned))
        assert "http://" not in source and "https://" not in source, name
        assert "api_key" not in source.lower(), name


def test_no_v3b_result_artifact_exists() -> None:
    for name in ("benchmark-v3-B.json", "benchmark-v3b.json"):
        assert not (ROOT / "benchmark" / name).exists(), name
