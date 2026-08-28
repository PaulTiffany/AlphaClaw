"""Offline tests for the controlled benchmark suite.

Nothing here touches a network, a provider, Omega, or a container. The screening
harness is imported and its selection logic exercised, but its request path is never
invoked except through an injected fake.
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
for extra in (SCRIPTS, ROOT / "ingress"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


suite = _load("benchmark_suite_mod", SCRIPTS / "make_benchmark_suite.py")
scorer = _load("score_handoff_mod", SCRIPTS / "score_handoff.py")
screen = _load("screen_sensory_mod", SCRIPTS / "screen_sensory_models.py")

# Pinned digests for the six deterministic stimuli.
PINNED = {
    "ocr_count": "9fffa97ac76f34c67694c02c7bb6cf6df13a2d887d88c62c98846d8d91904890",
    "colour_count": "291b75cdb85c3a501d57bb8723ffd5720b09d550ad4ab86686c208bfd5dfbc79",
    "spatial_relation": "9b3698376dc3b4cf3cf545f3f3eacc3cac1dcaa2a067f71df0f6067523d44f99",
    "number_arithmetic": "b09f90be93047df284a102ddb861062d8dac21c35784b0233b3030c197e29bfb",
    "distractor_selection": "68f0297b321d2f2ca5f82374255bb050a994ad7fc60660ec92b23537be914bcc",
    "multi_fact_composition": "63e1a1ebc4a8e64cff26adeff7155c50720d75b230d3fed4670ba65821bec753",
}


def _handoff(literal=(), entities=(), relations=()):
    return {
        "schema_version": 1,
        "observation": {
            "literal": list(literal),
            "entities": [{"label": e, "kind": "shape"} for e in entities],
            "relations": list(relations),
            "interpretations": [],
            "uncertainty": [],
            "unresolved": [],
        },
    }


# --- stimuli determinism ----------------------------------------------------


def test_suite_digests_are_pinned_and_deterministic() -> None:
    doc = suite.build_suite()
    for item in doc["items"]:
        assert item["image_sha256"] == PINNED[item["item_id"]], item["item_id"]
    assert suite.build_suite()["items"] == doc["items"]


def test_six_distinct_families() -> None:
    doc = suite.build_suite()
    assert len(doc["items"]) == 6
    assert len({i["item_id"] for i in doc["items"]}) == 6
    assert len({i["image_sha256"] for i in doc["items"]}) == 6


def test_every_rule_states_its_formatting_contract() -> None:
    """The direct fix for the K73 under-specification."""
    for item in suite.build_suite()["items"]:
        rule = item["rule_text"]
        assert "no spaces" in rule, item["item_id"]
        assert "no other text" in rule, item["item_id"]
        assert ("uppercase" in rule) or ("digits only" in rule), item["item_id"]


def test_arithmetic_item_is_labelled_a_resident_reasoning_probe() -> None:
    doc = suite.build_suite()
    probes = {i["item_id"]: i["probe"] for i in doc["items"]}
    assert probes["number_arithmetic"] == "resident_reasoning"
    assert all(v == "perception" for k, v in probes.items() if k != "number_arithmetic")


def test_text_control_supplies_facts_and_rule() -> None:
    for item in suite.build_suite()["items"]:
        assert item["rule_text"] in item["text_control_input"]
        assert item["text_control_sha256"] == hashlib.sha256(
            item["text_control_input"].encode("utf-8")
        ).hexdigest()


def test_ground_truth_totals() -> None:
    doc = suite.build_suite()
    assert doc["total_atomic_facts"] == sum(i["atomic_fact_count"] for i in doc["items"])
    assert doc["total_atomic_facts"] == 21


def test_generator_uses_only_the_standard_library() -> None:
    source = (SCRIPTS / "make_benchmark_suite.py").read_text(encoding="utf-8")
    for heavy in ("PIL", "Pillow", "numpy", "cv2", "matplotlib"):
        assert heavy not in source


# --- scorer: correct / incorrect / unknown ----------------------------------


def test_token_fact_correct_and_case_sensitive() -> None:
    fact = [{"type": "token", "value": "M4"}]
    assert scorer.score_item(_handoff(literal=["The token M4 is shown"]), fact)["correct"] == 1
    # lowercase must not satisfy a case-sensitive token fact
    assert scorer.score_item(_handoff(literal=["the token m4 is shown"]), fact)["correct"] == 0


def test_shape_presence_requires_same_assertion_string() -> None:
    fact = [{"type": "shape_presence", "colour": "blue", "shape": "square"}]
    assert scorer.score_item(_handoff(literal=["three blue squares"]), fact)["correct"] == 1
    split = _handoff(literal=["the colour blue is present", "there are squares"])
    assert scorer.score_item(split, fact)["correct"] == 0


def test_count_fact_accepts_digit_or_number_word() -> None:
    fact = [{"type": "shape_count", "colour": "blue", "shape": "square", "value": 3}]
    assert scorer.score_item(_handoff(literal=["Three blue squares"]), fact)["correct"] == 1
    assert scorer.score_item(_handoff(literal=["3 blue squares"]), fact)["correct"] == 1
    assert scorer.score_item(_handoff(entities=["three blue squares"]), fact)["correct"] == 1


def test_count_fact_wrong_count_is_incorrect() -> None:
    fact = [{"type": "shape_count", "colour": "blue", "shape": "square", "value": 3}]
    result = scorer.score_item(_handoff(literal=["Four blue squares"]), fact)
    assert result["correct"] == 0
    assert result["verdicts"][0]["verdict"] == scorer.INCORRECT


def test_count_fact_requires_co_occurrence_not_a_loose_number() -> None:
    fact = [{"type": "shape_count", "colour": "blue", "shape": "square", "value": 3}]
    loose = _handoff(literal=["there are 3 things", "blue squares appear"])
    assert scorer.score_item(loose, fact)["correct"] == 0


def test_relation_correct_via_declared_left_form() -> None:
    fact = [{
        "type": "relation", "subject_colour": "red", "subject_shape": "square",
        "predicate": "left_of", "object_colour": "blue", "object_shape": "square",
    }]
    h = _handoff(relations=[{
        "subject": "red square", "predicate": "is to the left of", "object": "blue square"
    }])
    assert scorer.score_item(h, fact)["verdicts"][0]["verdict"] == scorer.CORRECT


def test_relation_correct_via_inverted_right_form() -> None:
    fact = [{
        "type": "relation", "subject_colour": "red", "subject_shape": "square",
        "predicate": "left_of", "object_colour": "blue", "object_shape": "square",
    }]
    h = _handoff(relations=[{
        "subject": "blue square", "predicate": "is to the right of", "object": "red square"
    }])
    assert scorer.score_item(h, fact)["verdicts"][0]["verdict"] == scorer.CORRECT


def test_relation_contradiction_is_incorrect() -> None:
    fact = [{
        "type": "relation", "subject_colour": "red", "subject_shape": "square",
        "predicate": "left_of", "object_colour": "blue", "object_shape": "square",
    }]
    h = _handoff(relations=[{
        "subject": "blue square", "predicate": "is to the left of", "object": "red square"
    }])
    assert scorer.score_item(h, fact)["verdicts"][0]["verdict"] == scorer.INCORRECT


def test_relation_unmapped_predicate_is_unknown_not_guessed() -> None:
    """The scorer refuses to interpret free prose; it reports coverage instead."""
    fact = [{
        "type": "relation", "subject_colour": "red", "subject_shape": "square",
        "predicate": "left_of", "object_colour": "blue", "object_shape": "square",
    }]
    h = _handoff(relations=[{
        "subject": "red square", "predicate": "sits near", "object": "blue square"
    }])
    result = scorer.score_item(h, fact)
    assert result["verdicts"][0]["verdict"] == scorer.UNKNOWN
    assert result["scoreable"] == 0
    assert result["scoring_coverage"] == 0.0
    assert result["atomic_fact_accuracy"] is None
    assert result["atomic_fact_yield"] == 0.0


def test_non_schema_handoff_scores_zero_correct_not_unknown() -> None:
    """A contract failure is evidence, so it must not vanish into 'unknown'."""
    facts = [{"type": "token", "value": "M4"},
             {"type": "shape_presence", "colour": "blue", "shape": "square"}]
    for bad in (None, "not json", {"no_observation": True}, {"observation": "wrong type"}):
        result = scorer.score_item(bad, facts)
        assert result["schema_conformant"] is False
        assert result["correct"] == 0
        assert result["scoreable"] == 2
        assert all(v["verdict"] == scorer.INCORRECT for v in result["verdicts"])


def test_interpretations_are_not_read_as_assertions() -> None:
    """Only literal observations and entity labels are scoreable evidence."""
    fact = [{"type": "token", "value": "M4"}]
    h = _handoff()
    h["observation"]["interpretations"] = ["probably the token M4"]
    assert scorer.score_item(h, fact)["correct"] == 0


def test_coverage_reported_separately_from_accuracy() -> None:
    facts = [
        {"type": "token", "value": "M4"},
        {"type": "relation", "subject_colour": "red", "subject_shape": "square",
         "predicate": "left_of", "object_colour": "blue", "object_shape": "square"},
    ]
    h = _handoff(literal=["token M4"], relations=[{"subject": "a", "predicate": "near", "object": "b"}])
    result = scorer.score_item(h, facts)
    assert result["correct"] == 1
    assert result["scoreable"] == 1
    assert result["atomic_fact_accuracy"] == 1.0     # over scoreable facts
    assert result["atomic_fact_yield"] == 0.5        # over all expected facts
    assert result["scoring_coverage"] == 0.5


# --- selection rule ---------------------------------------------------------


def test_selection_rule_prefers_highest_yield() -> None:
    chosen = scorer.select_sensory_model([
        {"model_id": "b", "atomic_fact_yield": 0.9, "schema_compliance_rate": 0.5,
         "repeat_stability": 0.1, "mean_output_tokens": 900},
        {"model_id": "a", "atomic_fact_yield": 0.8, "schema_compliance_rate": 1.0,
         "repeat_stability": 1.0, "mean_output_tokens": 100},
    ])
    assert chosen["model_id"] == "b"


def test_selection_rule_tiebreaks_in_declared_order() -> None:
    base = {"atomic_fact_yield": 0.8}
    # tie on yield -> schema compliance wins
    assert scorer.select_sensory_model([
        {"model_id": "x", **base, "schema_compliance_rate": 0.5, "repeat_stability": 1.0, "mean_output_tokens": 10},
        {"model_id": "y", **base, "schema_compliance_rate": 1.0, "repeat_stability": 0.0, "mean_output_tokens": 99},
    ])["model_id"] == "y"
    # tie on yield+schema -> stability wins
    assert scorer.select_sensory_model([
        {"model_id": "x", **base, "schema_compliance_rate": 1.0, "repeat_stability": 0.2, "mean_output_tokens": 10},
        {"model_id": "y", **base, "schema_compliance_rate": 1.0, "repeat_stability": 0.9, "mean_output_tokens": 99},
    ])["model_id"] == "y"
    # tie further -> lowest mean output tokens
    assert scorer.select_sensory_model([
        {"model_id": "x", **base, "schema_compliance_rate": 1.0, "repeat_stability": 0.9, "mean_output_tokens": 500},
        {"model_id": "y", **base, "schema_compliance_rate": 1.0, "repeat_stability": 0.9, "mean_output_tokens": 100},
    ])["model_id"] == "y"
    # residual tie -> lexicographically lowest id
    assert scorer.select_sensory_model([
        {"model_id": "zeta", **base, "schema_compliance_rate": 1.0, "repeat_stability": 0.9, "mean_output_tokens": 100},
        {"model_id": "alpha", **base, "schema_compliance_rate": 1.0, "repeat_stability": 0.9, "mean_output_tokens": 100},
    ])["model_id"] == "alpha"


def test_schema_failures_do_not_exclude_a_model() -> None:
    """A model failing schema on some images stays in contention, penalised by yield."""
    chosen = scorer.select_sensory_model([
        {"model_id": "partial", "atomic_fact_yield": 0.7, "schema_compliance_rate": 0.5,
         "repeat_stability": 0.5, "mean_output_tokens": 200},
        {"model_id": "clean", "atomic_fact_yield": 0.6, "schema_compliance_rate": 1.0,
         "repeat_stability": 1.0, "mean_output_tokens": 200},
    ])
    assert chosen["model_id"] == "partial"


def test_selection_rule_text_is_pre_registered() -> None:
    rule = scorer.SELECTION_RULE
    for phrase in ("atomic-fact yield", "schema-compliance rate", "repeat stability",
                   "lowest mean output tokens", "lexicographically lowest"):
        assert phrase in rule


# --- screening harness safety ----------------------------------------------


def test_router_alias_is_rejected_as_a_benchmark_condition() -> None:
    with pytest.raises(ValueError, match="nondeterministic router"):
        screen.screen_model("openrouter/free", [], Path("."), "key", 1)


def test_candidate_models_are_explicit_ids() -> None:
    assert "openrouter/free" not in screen.CANDIDATE_MODELS
    assert screen.CANDIDATE_MODELS == (
        "dots-studio/dots-3-note-preview:free",
        "google/gemma-4-26b-a4b-it:free",
        "google/gemma-4-31b-it:free",
    )


def _code_without_module_docstring(path: Path) -> str:
    """Source with the module docstring removed, for case-insensitive code checks.

    Strips by AST line range rather than by string replacement: a docstring
    containing escape sequences does not match its own source text.
    """
    import ast

    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    if tree.body and isinstance(tree.body[0], ast.Expr):
        node = tree.body[0].value
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            del lines[node.lineno - 1 : node.end_lineno]
    return chr(10).join(lines)


def test_screening_never_references_the_reasoning_provider() -> None:
    """Case-insensitive, and over code rather than prose.

    The module docstring legitimately says it never touches ASICloud; a
    case-sensitive check over the whole file would pass even if the code did.
    """
    code = _code_without_module_docstring(SCRIPTS / "screen_sensory_models.py").lower()
    for token in ("asicloud", "asi_api_key", "omegaboi", "docker", "minimax"):
        assert token not in code, token


def test_screening_counts_a_failed_call_as_zero_correct_facts(tmp_path: Path) -> None:
    """A request failure is benchmark evidence, kept in the denominator."""
    def exploding_runner(image, model, api_key):
        raise RuntimeError("upstream refused")

    items = [{"item_id": "x", "image_filename": "x.png",
              "facts": [{"type": "token", "value": "M4"}]}]
    result = screen.screen_model("some/model:free", items, tmp_path, "key", 1,
                                 runner=exploding_runner)
    assert result["request_failures"] == 1
    assert result["correct_facts"] == 0
    assert result["expected_facts"] == 1
    assert result["atomic_fact_yield"] == 0.0


def test_screening_uses_the_frozen_sensory_boundary() -> None:
    source = (SCRIPTS / "screen_sensory_models.py").read_text(encoding="utf-8")
    assert "import openrouter_image" in source
    assert "SYSTEM_PROMPT" not in source, "screening must not redefine the sensory prompt"


def test_sensory_system_prompt_is_unmodified() -> None:
    """The boundary under test is frozen for this benchmark."""
    source = (ROOT / "ingress" / "openrouter_image.py").read_text(encoding="utf-8")
    assert "AlphaClaw's perception boundary" in source
    assert '"response_format": {"type": "json_object"}' in source


# --- sponsor condition is a fixed condition, not a tuning target ------------


def test_reasoning_condition_is_recorded_as_fixed() -> None:
    cond = suite.build_suite()["reasoning_condition"]
    assert cond["provider"] == "asicloud"
    assert cond["model"] == "minimax/minimax-m3"
    assert cond["max_new_input_loops"] == 1
    assert cond["max_wake_loops"] == 0
    assert cond["max_history"] == 0
    assert "not a benchmark-tuning target" in cond["note"]


def test_no_item_mentions_the_reasoning_model() -> None:
    """Stimuli and rules must be independent of the resident model."""
    doc = suite.build_suite()
    blob = json.dumps(doc["items"]).lower()
    for token in ("minimax", "asicloud", "asi cloud", "sponsor"):
        assert token not in blob, token


def test_scorer_is_independent_of_the_reasoning_model() -> None:
    source = (SCRIPTS / "score_handoff.py").read_text(encoding="utf-8")
    for token in ("minimax", "asicloud", "openrouter"):
        assert token not in source.lower(), token
