"""Protocol v3 preregistration -- offline design checks.

No network, no container, no provider call, no result artifact. These tests pin the
frozen preregistration and prove the design is internally consistent, that v2 is
untouched, and that the representation transforms are deterministic and leak-free.
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
INGRESS = ROOT / "ingress"
for extra in (SCRIPTS, INGRESS, ROOT / "controller"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import economics_v3
import instruction_receipt
import pipe
import protocol_v3
import representation_v3


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


episode_contract = _load("episode_contract_v3", ROOT / "controller" / "episode_contract.py")
v2 = _load("protocol_v2_v3", SCRIPTS / "protocol_v2.py")

ARTIFACT = ROOT / "benchmark" / "protocol-v3.json"
ARTIFACT_SHA = "d183b8f38e89a0380f543642535d02172220951e4922c55cadca847991d47d39"

V2_DIGESTS = {
    "protocol-v2.json": "b5ee0c3760a9540119526f1c51ac1dc5cc0d6fadc0fe1e378ddf770d3d02557f",
    "screening-v2-B1.json": "847828d469d60269a289f5183d07a69c6afc4c123ef1ad51346490e778e0ab14",
    "benchmark-v2-A.json": "644f36e406df5520f54e6bcb706b891e9dd1ff9094c6c0d59cfb305e68be65ea",
    "benchmark-v2-B2.json": "8b6cc4557b27c8cc2acf7803ca05293b0fd39ca1fe1cc6f89dbe838045fd7d48",
    "benchmark-v2-C.json": "b46ea2ceb4429c15bd3fa5b422d4e47e5a3acdb70467b6c5a3960eee090f6c88",
}

DIAGNOSTIC_ITEMS = ("distractor_selection", "number_arithmetic")


@pytest.fixture(scope="module")
def items():
    raw = json.loads((ROOT / "benchmark" / "items.json").read_text(encoding="utf-8"))
    return {i["item_id"]: i for i in raw["items"]}


@pytest.fixture(scope="module")
def condition_a():
    raw = json.loads(
        (ROOT / "benchmark" / "benchmark-v2-A.json").read_text(encoding="utf-8"))
    return {(r["item_id"], r["condition"]): r for r in raw["runs"]}


@pytest.fixture(scope="module")
def spec():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


# --- the artifact is a preregistration, not a result --------------------------


def test_artifact_digest_is_frozen() -> None:
    assert hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() == ARTIFACT_SHA


def test_artifact_matches_the_module(spec) -> None:
    """Round-trip the module output: tuples serialise to lists, so compare as JSON."""
    regenerated = json.loads(json.dumps(protocol_v3.specification(), sort_keys=True))
    assert spec == regenerated


def test_artifact_declares_itself_a_preregistration(spec) -> None:
    assert spec["protocol_version"] == "v3"
    assert "no result recorded" in spec["status"]
    blob = json.dumps(spec).lower()
    for banned in ("exact_match_rate\":", "\"response\":", "observed_accuracy"):
        assert banned not in blob, banned


def test_no_v3_result_artifact_exists() -> None:
    for name in ("benchmark-v3-A.json", "benchmark-v3-B.json",
                 "benchmark-v3.json", "screening-v3.json"):
        assert not (ROOT / "benchmark" / name).exists(), name


# --- v2 is untouched ----------------------------------------------------------


def test_every_v2_artifact_digest_unchanged() -> None:
    for name, expected in V2_DIGESTS.items():
        actual = hashlib.sha256(
            (ROOT / "benchmark" / name).read_bytes()).hexdigest()
        assert actual == expected, name


def test_v2_scorer_and_lexicon_unchanged() -> None:
    scorer = (SCRIPTS / "score_handoff.py").read_text(encoding="utf-8")
    assert "is located to the left of" not in scorer
    assert hashlib.sha256(scorer.encode("utf-8")).hexdigest() == (
        "54fca8997f1f0dea9555b5b91f145d477c8b3172b4bc09a590b35454f6191699")


def test_v2_asicloud_cap_not_raised_or_reused() -> None:
    assert v2.ASICLOUD_MAX_CALLS == 42
    caps = protocol_v3.specification()["caps"]
    assert "untouched" in caps["v2_asicloud_allocation"]
    assert caps["V3A_asicloud_calls"] != v2.ASICLOUD_MAX_CALLS


def test_v2_item_digests_untouched(items) -> None:
    """V3-B extends the generator in a new module; v2 stimuli must not move."""
    assert items["distractor_selection"]["image_sha256"] == (
        "68f0297b321d2f2ca5f82374255bb050a994ad7fc60660ec92b23537be914bcc")
    assert items["number_arithmetic"]["image_sha256"] == (
        "b09f90be93047df284a102ddb861062d8dac21c35784b0233b3030c197e29bfb")


# --- V3-A matrix --------------------------------------------------------------


def test_v3a_plan_is_internally_consistent() -> None:
    protocol_v3.validate()
    budget = protocol_v3.v3a_call_budget()
    assert budget["runs"] == 18
    assert budget["asicloud_calls"] == 20 <= protocol_v3.V3A_ASICLOUD_MAX_CALLS
    assert budget["openrouter_resident_calls"] == 25 <= protocol_v3.V3A_OPENROUTER_MAX_CALLS
    assert budget["sensory_calls"] == 0


def test_v3a_makes_no_new_sensory_call() -> None:
    assert protocol_v3.V3A_SENSORY_MAX_CALLS == 0
    for run in protocol_v3.v3a_runs():
        assert run["sensory_calls"] == 0


def test_v3a_uses_only_already_observed_failures(spec) -> None:
    cases = spec["sections"]["V3A"]["cases"]
    assert {c["item_id"] for c in cases} == set(DIAGNOSTIC_ITEMS)
    for case in cases:
        assert case["observed_v2_failure"]
    assert "NOT a representative accuracy benchmark" in \
        spec["sections"]["V3A"]["population_note"]


def test_v3a_turn_budgets_keep_one_turn_as_the_baseline(spec) -> None:
    section = spec["sections"]["V3A"]
    assert section["turn_budgets"] == [1, 2]
    assert section["baseline_turn_budget"] == 1
    assert "not the AlphaClaw population" in section["two_turn_role"]


def test_v3a_run_call_counts_follow_the_turn_budget() -> None:
    for run in protocol_v3.v3a_runs():
        assert run["boot_calls"] == 1
        assert run["max_episode_calls"] == run["turn_budget"]
        assert run["max_provider_calls"] == 1 + run["turn_budget"]


def test_v3a_interpretation_matrix_is_frozen_and_non_committal(spec) -> None:
    matrix = spec["sections"]["V3A"]["interpretation_matrix"]
    readings = " ".join(row["reading"] for row in matrix).lower()
    for factor in ("representation richness", "representation form",
                   "task structure", "scheduling constraint",
                   "output-channel", "information preservation"):
        assert factor in readings, factor
    assert "universal cause" in spec["sections"]["V3A"]["interpretation_limit"]


def test_v3a_residents_are_the_two_that_produced_the_observed_failures() -> None:
    assert protocol_v3.V3A_RESIDENT_MINIMAX == ("asicloud", "minimax/minimax-m3")
    assert protocol_v3.V3A_RESIDENT_GEMMA == ("openrouter", "google/gemma-4-26b-a4b-it")


def test_a3_native_text_control_has_no_representation_factor() -> None:
    a3 = [r for r in protocol_v3.v3a_runs() if r["case_id"] == "A3"]
    assert len(a3) == 2
    assert all(r["representation"] is None for r in a3)


# --- representation transforms ------------------------------------------------


@pytest.mark.parametrize("item_id", DIAGNOSTIC_ITEMS)
def test_r1_reproduces_the_frozen_v2_payload_byte_for_byte(
        item_id, items, condition_a) -> None:
    """R1 must be the CURRENT representation, not a re-rendering of it."""
    a_run = condition_a[(item_id, "image_text")]
    handoff = json.loads(a_run["payload"])["sensory_handoff"]
    rendered = representation_v3.render(
        representation_v3.R1_FULL_SYMBOLIC,
        human_text=items[item_id]["rule_text"], full_handoff=handoff)
    assert rendered == a_run["payload"]


@pytest.mark.parametrize("item_id", DIAGNOSTIC_ITEMS)
@pytest.mark.parametrize("variant", [representation_v3.R2_MINIMAL_SYMBOLIC,
                                     representation_v3.R3_PLAIN_LANGUAGE,
                                     representation_v3.R4_TASK_STRUCTURED])
def test_no_variant_leaks_the_expected_answer(item_id, variant, items) -> None:
    item = items[item_id]
    payload = representation_v3.render(
        variant, human_text=item["rule_text"],
        facts=representation_v3.required_facts(item))
    assert not representation_v3.leaks_answer(payload, item["expected_answer"])


@pytest.mark.parametrize("item_id", DIAGNOSTIC_ITEMS)
def test_transforms_are_deterministic(item_id, items) -> None:
    item = items[item_id]
    facts = representation_v3.required_facts(item)
    for variant in (representation_v3.R2_MINIMAL_SYMBOLIC,
                    representation_v3.R3_PLAIN_LANGUAGE,
                    representation_v3.R4_TASK_STRUCTURED):
        first = representation_v3.render(variant, human_text=item["rule_text"],
                                         facts=facts)
        second = representation_v3.render(variant, human_text=item["rule_text"],
                                          facts=list(reversed(list(reversed(facts)))))
        assert first == second


@pytest.mark.parametrize("item_id", DIAGNOSTIC_ITEMS)
def test_every_variant_carries_the_same_task_instruction_bytes(item_id, items) -> None:
    item = items[item_id]
    facts = representation_v3.required_facts(item)
    instruction = item["rule_text"]
    for variant in (representation_v3.R2_MINIMAL_SYMBOLIC,
                    representation_v3.R3_PLAIN_LANGUAGE,
                    representation_v3.R4_TASK_STRUCTURED):
        payload = json.loads(representation_v3.render(
            variant, human_text=instruction, facts=facts))
        carried = payload.get("human_text") or payload.get("task_instruction")
        assert carried == instruction, variant


@pytest.mark.parametrize("item_id", DIAGNOSTIC_ITEMS)
def test_all_required_facts_survive_every_variant(item_id, items) -> None:
    """Information content is held constant; only form varies."""
    item = items[item_id]
    facts = representation_v3.required_facts(item)
    r2 = json.loads(representation_v3.render(
        representation_v3.R2_MINIMAL_SYMBOLIC, human_text=item["rule_text"],
        facts=facts))
    r4 = json.loads(representation_v3.render(
        representation_v3.R4_TASK_STRUCTURED, human_text=item["rule_text"],
        facts=facts))
    assert r2["symbolic_facts"] == facts
    assert r4["observations"] == facts

    sentences = representation_v3.plain_language(facts)
    for fact in facts:
        if fact["type"] == "number":
            assert str(fact["value"]) in sentences
        if fact["type"] in ("shape_presence", "shape_count"):
            assert fact["colour"] in sentences and fact["shape"] in sentences


def test_plain_language_uses_no_summariser_and_is_total() -> None:
    source = (SCRIPTS / "representation_v3.py").read_text(encoding="utf-8")
    lowered = source.lower()
    for token in ("requests", "urllib", "openrouter", "api_key", "random."):
        assert token not in lowered, token
    # no model, no scorer, no ingress: the renderer imports nothing that can infer
    imports = [line for line in source.splitlines()
               if line.startswith(("import ", "from "))]
    assert imports == ["from __future__ import annotations", "import json",
                       "from typing import Any"], imports
    with pytest.raises(representation_v3.RepresentationError):
        representation_v3.render_fact_sentence({"type": "not_a_frozen_type"})


def test_r3_renders_counts_with_frozen_words() -> None:
    facts = [{"type": "shape_count", "colour": "blue", "shape": "square", "value": 4},
             {"type": "shape_count", "colour": "red", "shape": "square", "value": 1}]
    assert representation_v3.plain_language(facts) == (
        "There are four blue squares. There is one red square.")


def test_relation_rendering_is_independent_of_the_scorer_lexicon() -> None:
    """R3 phrasing is rendering-only. It must not import, feed or widen the scorer.

    Note the frozen scorer ALREADY accepts "is to the left of"; the invariant here is
    not that the phrases are absent from it, but that the renderer cannot influence it.
    """
    source = (SCRIPTS / "representation_v3.py").read_text(encoding="utf-8")
    assert "score_handoff" not in source
    assert "LEFT_OF_FORMS" not in source and "RIGHT_OF_FORMS" not in source
    # the scorer file itself is pinned by digest elsewhere; confirm it is unmodified
    scorer = (SCRIPTS / "score_handoff.py").read_text(encoding="utf-8")
    assert "is located to the left of" not in scorer


# --- instruction-position receipt ---------------------------------------------


def test_receipt_locates_every_component_in_a_real_frozen_envelope(
        items, condition_a) -> None:
    a_run = condition_a[("distractor_selection", "image_text")]
    contract = episode_contract.EpisodeContract(max_reasoning_loops=1).handoff()
    envelope = pipe.alpha_prepend.prepend(a_run["payload"], episode_contract=contract)
    receipt = instruction_receipt.positions(
        envelope,
        alpha_instruction=json.loads(envelope)["contract"][0],
        human_task=items["distractor_selection"]["rule_text"],
        symbolic_evidence=json.dumps(
            json.loads(a_run["payload"])["sensory_handoff"],
            ensure_ascii=False, sort_keys=True))
    assert receipt["all_components_found"] is True
    assert receipt["order"] == ["alpha_instruction", "human_task", "symbolic_evidence"]
    assert receipt["alpha_instruction_precedes_human_task"] is True
    assert receipt["components"]["symbolic_evidence"]["matched_form"] == "json_escaped"
    assert receipt["chars_between_alpha_instruction_and_human_task"] > 0


def test_receipt_reports_positions_not_a_salience_score() -> None:
    receipt = instruction_receipt.positions(
        "AAABBBCCC", alpha_instruction="AAA", human_task="BBB",
        symbolic_evidence="CCC")
    assert receipt["salience_score_reported"] is False
    assert receipt["per_segment_tokens_available"] is False
    assert receipt["request_tokens"] is None
    summary = instruction_receipt.distance_summary(receipt)
    assert summary["alpha_instruction_chars_before"] == 0
    assert summary["human_task_chars_before"] == 3
    assert summary["human_task_chars_after"] == 3
    source = (SCRIPTS / "instruction_receipt.py").read_text(encoding="utf-8").lower()
    for token in ("salience_score", "importance", "attention_weight"):
        assert f"def {token}" not in source


def test_receipt_records_a_missing_component_rather_than_guessing() -> None:
    receipt = instruction_receipt.positions("only alpha here",
                                            alpha_instruction="only alpha")
    assert receipt["all_components_found"] is False
    assert receipt["components"]["human_task"]["found"] is False
    assert receipt["chars_between_alpha_instruction_and_human_task"] is None


# --- V3-B matrix and economics ------------------------------------------------


def test_v3b_plan_is_internally_consistent() -> None:
    budget = protocol_v3.v3b_call_budget()
    assert budget["depths"] == [1, 2, 4, 8]
    assert budget["multimodal_calls"] == 38 <= protocol_v3.V3B_MULTIMODAL_MAX_CALLS
    assert budget["text_calls"] == 60 <= protocol_v3.V3B_TEXT_MAX_CALLS
    assert budget["total_calls"] == 98 == protocol_v3.V3B_MAX_CALLS


def test_v3b_uses_one_model_for_every_arm_to_remove_the_price_confound(spec) -> None:
    section = spec["sections"]["V3B"]
    assert section["model"]["model"] == "qwen/qwen3.7-flash"
    assert set(section["model"]["used_by"]) == set(economics_v3.ARCHITECTURES)
    assert "only input modality per call varies" in section["fairness_rule"]
    assert "never presented as" in section["fairness_rule"]


def test_v3b_discloses_that_e1_is_not_alphaclaw(spec) -> None:
    note = spec["sections"]["V3B"]["harness_note"]
    assert "E1 is not AlphaClaw" in note
    assert "ESTIMATE" in note


def test_expected_call_structure_is_architectural_arithmetic() -> None:
    for depth, avoided, fraction in ((1, 0, 0.0), (2, 1, 0.5),
                                     (4, 3, 0.75), (8, 7, 0.875)):
        structure = economics_v3.expected_call_structure(depth)
        assert structure["multimodal_calls_avoided"] == avoided
        assert structure["multimodal_avoidance_fraction"] == pytest.approx(fraction)
        assert structure[economics_v3.E1_MULTIMODAL_RESIDENT]["multimodal_calls"] == depth
        assert structure[economics_v3.E2_ALPHACLAW]["multimodal_calls"] == 1
        assert structure[economics_v3.E3_TEXT_ORACLE]["multimodal_calls"] == 0
        assert "not an empirical result" in structure["label"]


def test_receipts_are_checked_against_the_expected_structure() -> None:
    ok = economics_v3.receipts_match_expected(
        depth=4, architecture=economics_v3.E2_ALPHACLAW,
        multimodal_calls=1, text_calls=4)
    assert ok["matches"] is True
    bad = economics_v3.receipts_match_expected(
        depth=4, architecture=economics_v3.E2_ALPHACLAW,
        multimodal_calls=2, text_calls=4)
    assert bad["matches"] is False


def test_frozen_cost_equations() -> None:
    c_mm, c_text = 0.010, 0.001
    assert economics_v3.cost_multimodal_resident(4, c_mm) == pytest.approx(0.040)
    assert economics_v3.cost_alphaclaw(4, c_mm, c_text) == pytest.approx(0.013)
    assert economics_v3.savings(4, c_mm, c_text) == pytest.approx(0.027)
    assert economics_v3.savings_fraction(4, c_mm, c_text) == pytest.approx(0.675)
    assert economics_v3.stationary_limit(c_mm, c_text) == pytest.approx(0.9)
    assert economics_v3.savings(1, c_mm, c_text) == 0
    assert economics_v3.savings_fraction(1, c_mm, c_text) == pytest.approx(0.0)


def test_cost_per_success_is_undefined_at_zero_successes() -> None:
    zero = economics_v3.cost_per_successful_episode(
        total_cost=0.01, successful_episodes=0, provenance=economics_v3.MEASURED)
    assert zero["cost_per_successful_episode"] is None
    assert zero["defined"] is False
    assert "not economically superior" in zero["note"]


def test_a_cheaper_failing_architecture_never_wins() -> None:
    """The v2 resident-substitution result is exactly why this rule exists."""
    cheap_but_failing = {**economics_v3.cost_per_successful_episode(
        total_cost=0.001, successful_episodes=0,
        provenance=economics_v3.MEASURED), "label": "cheap_failer"}
    costlier_but_working = {**economics_v3.cost_per_successful_episode(
        total_cost=0.010, successful_episodes=5,
        provenance=economics_v3.MEASURED), "label": "works"}
    assert economics_v3.economically_superior(
        cheap_but_failing, costlier_but_working) is None


def test_cost_provenance_must_be_declared() -> None:
    with pytest.raises(economics_v3.EconomicsError):
        economics_v3.cost_per_successful_episode(
            total_cost=1.0, successful_episodes=1, provenance="guessed")


def test_economics_module_makes_no_provider_call() -> None:
    source = (SCRIPTS / "economics_v3.py").read_text(encoding="utf-8").lower()
    for token in ("requests", "urllib", "socket", "subprocess", "docker", "api_key"):
        assert token not in source, token


# --- budgets, policy, stop conditions -----------------------------------------


def test_total_projected_calls(spec) -> None:
    totals = protocol_v3.total_projected_calls()
    assert totals == {
        "V3A_asicloud": 20, "V3A_openrouter_resident": 25, "V3A_sensory": 0,
        "V3B_multimodal": 38, "V3B_text": 60, "grand_total": 143,
    }
    assert spec["total_projected_calls"] == totals


def test_hard_caps_are_declared(spec) -> None:
    caps = spec["caps"]
    assert caps["V3A_sensory_calls"] == 0
    assert caps["max_cost_usd"] == 2.50
    assert caps["V3A_max_cost_usd"] == 0.50
    assert caps["V3B_max_cost_usd"] == 2.00
    assert caps["max_input_tokens"] == 520_000
    assert caps["max_output_tokens"] == 230_000


def test_policy_forbids_fallback_retry_and_retro_tuning(spec) -> None:
    policy = " ".join(spec["policy"]).lower()
    for rule in ("no automatic model fallback", "no retry-until-pass",
                 "availability failures remain evidence",
                 "no prompt tuning after results",
                 "no changing representation rules after observing results",
                 "no broadening the v2 scorer retrospectively",
                 "no llm judge"):
        assert rule in policy, rule


def test_sections_are_independent(spec) -> None:
    assert "never combined" in spec["independence"]
    assert "neither tunes the other" in spec["independence"]


def test_stop_conditions_cover_the_dangerous_paths(spec) -> None:
    stops = " ".join(spec["stop_conditions"]).lower()
    for condition in ("artifact digest mismatch", "pin mismatch", "image id changed",
                      "leaks the item's exact expected answer", "call cap",
                      "token or dollar cap", "availability failure"):
        assert condition in stops, condition


def test_no_forbidden_model_in_the_matrix(spec) -> None:
    blob = json.dumps(spec)
    for forbidden in protocol_v3.FORBIDDEN_MODELS:
        assert forbidden not in blob, forbidden


def test_no_new_scorer_is_introduced(spec) -> None:
    scoring = spec["scoring"]
    assert scoring["new_scorer_introduced"] is False
    assert scoring["llm_judge"] is False
    assert scoring["sensory_scorer"].endswith("unchanged and not broadened")
