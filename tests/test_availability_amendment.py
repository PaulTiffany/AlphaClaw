"""Protocol Amendment v1.1 -- provider-availability recovery.

Offline. No network, no provider, no container.

These tests fix the amendment's boundary: availability failures may be measured once
more, genuine experimental outcomes may not, and Screening v1 is immutable.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

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


recovery = _load("availability_recovery_mod", SCRIPTS / "availability_recovery.py")
suite = _load("benchmark_suite_amend", SCRIPTS / "make_benchmark_suite.py")
screen = _load("screen_sensory_amend", SCRIPTS / "screen_sensory_models.py")

SCREENING_V1 = ROOT / "benchmark" / "screening.json"

RATE_LIMIT_ERROR = (
    'RuntimeError: OpenRouter ingress failed: HTTP 429: {"error":{"message":'
    '"Provider returned error","code":429,"metadata":{"raw":'
    '"google/gemma-4-26b-a4b-it:free is temporarily rate-limited upstream."}}}'
)
SCHEMA_ERROR = "TypeError: handoff field 'literal_observations' must be an array of strings"


def _screening(calls):
    return {"candidates": [{"model_id": "m/x:free", "calls_detail": calls}]}


def _call(item, repeat, ok=True, error=None):
    return {"item_id": item, "repeat_index": repeat, "request_success": ok, "error": error}


# --- classification ---------------------------------------------------------


def test_http_429_is_an_availability_failure() -> None:
    assert recovery.classify_failure(RATE_LIMIT_ERROR) == recovery.AVAILABILITY


def test_schema_contract_failure_is_experimental_not_availability() -> None:
    """It reached inference and produced an outcome, so it is a result."""
    assert recovery.classify_failure(SCHEMA_ERROR) == recovery.EXPERIMENTAL


def test_other_errors_are_experimental() -> None:
    for err in ("RuntimeError: non-JSON response",
                "TypeError: multimodal handoff must be a JSON object",
                "RuntimeError: OpenRouter ingress failed: HTTP 500: server error"):
        assert recovery.classify_failure(err) == recovery.EXPERIMENTAL


def test_no_error_is_none() -> None:
    assert recovery.classify_failure(None) == recovery.NONE
    assert recovery.classify_failure("") == recovery.NONE


# --- eligibility ------------------------------------------------------------


def test_only_availability_cells_are_eligible() -> None:
    s = _screening([
        _call("a", 0, ok=False, error=RATE_LIMIT_ERROR),
        _call("b", 0, ok=False, error=SCHEMA_ERROR),
        _call("c", 0, ok=True),
    ])
    eligible = recovery.eligible_cells(s)
    assert [c["item_id"] for c in eligible] == ["a"]


def test_schema_failure_cell_is_never_retried() -> None:
    """The dots spatial_relation failure stays as the outcome for its cell."""
    s = _screening([_call("spatial_relation", 1, ok=False, error=SCHEMA_ERROR)])
    assert recovery.eligible_cells(s) == []
    assert recovery.build_recovery_plan(s) == []


def test_successful_cell_is_never_retried() -> None:
    s = _screening([_call("ocr_count", 0, ok=True)])
    assert recovery.build_recovery_plan(s) == []


# --- one replacement per cell ----------------------------------------------


def test_at_most_one_replacement_per_availability_cell() -> None:
    s = _screening([_call("a", 0, ok=False, error=RATE_LIMIT_ERROR)])
    first = recovery.build_recovery_plan(s)
    assert len(first) == 1

    already = [{"model_id": "m/x:free", "item_id": "a", "repeat_index": 0}]
    assert recovery.build_recovery_plan(s, already_recovered=already) == []


def test_repeat_cells_are_tracked_independently() -> None:
    s = _screening([
        _call("a", 0, ok=False, error=RATE_LIMIT_ERROR),
        _call("a", 1, ok=False, error=RATE_LIMIT_ERROR),
    ])
    already = [{"model_id": "m/x:free", "item_id": "a", "repeat_index": 0}]
    remaining = recovery.build_recovery_plan(s, already_recovered=already)
    assert [c["repeat_index"] for c in remaining] == [1]


def test_replacement_supersedes_only_on_an_experimental_outcome() -> None:
    assert recovery.supersedes({"request_success": True}) is True
    assert recovery.supersedes({"request_success": False, "error": SCHEMA_ERROR}) is True
    # a replacement that itself hit rate limiting supersedes nothing
    assert recovery.supersedes({"request_success": False, "error": RATE_LIMIT_ERROR}) is False


# --- availability reporting -------------------------------------------------


def test_availability_reported_separately_from_experimental() -> None:
    s = _screening([
        _call("a", 0, ok=False, error=RATE_LIMIT_ERROR),
        _call("b", 0, ok=False, error=SCHEMA_ERROR),
        _call("c", 0, ok=True),
    ])
    rep = recovery.availability_report(s)["per_model"]["m/x:free"]
    assert rep["attempted"] == 3
    assert rep["availability_failures"] == 1
    assert rep["experimental_failures"] == 1
    # a schema failure is a usable observation; a 429 is not
    assert rep["usable_observations"] == 2
    assert rep["availability_rate"] == 1 / 3


def test_real_screening_v1_availability_split() -> None:
    """Against the preserved Screening v1 artifact."""
    s = json.loads(SCREENING_V1.read_text(encoding="utf-8"))
    rep = recovery.availability_report(s)
    assert rep["totals"]["attempted"] == 36
    assert rep["totals"]["availability_failures"] == 24
    # 11 successes + 1 schema failure for dots
    assert rep["totals"]["usable_observations"] == 12
    assert rep["totals"]["availability_rate"] == 24 / 36


def test_real_screening_v1_eligible_cells_are_the_24_rate_limited() -> None:
    s = json.loads(SCREENING_V1.read_text(encoding="utf-8"))
    cells = recovery.eligible_cells(s)
    assert len(cells) == 24
    assert {c["model_id"] for c in cells} == {
        "google/gemma-4-26b-a4b-it:free",
        "google/gemma-4-31b-it:free",
    }
    # the dots schema failure is excluded
    assert all("dots-studio" not in c["model_id"] for c in cells)


# --- immutability -----------------------------------------------------------


def test_screening_v1_is_not_mutated_by_recovery_functions() -> None:
    before = json.loads(SCREENING_V1.read_text(encoding="utf-8"))
    snapshot = copy.deepcopy(before)
    recovery.eligible_cells(before)
    recovery.availability_report(before)
    recovery.build_recovery_plan(before)
    assert before == snapshot


def test_screening_v1_file_digest_is_stable_across_recovery_calls() -> None:
    digest = hashlib.sha256(SCREENING_V1.read_bytes()).hexdigest()
    s = json.loads(SCREENING_V1.read_text(encoding="utf-8"))
    recovery.build_recovery_plan(s)
    recovery.build_recovery_artifact(
        original_path=SCREENING_V1,
        protocol_commit="c78c08f",
        amendment_commit="pending",
        recovered_calls=[],
        screening=s,
    )
    assert hashlib.sha256(SCREENING_V1.read_bytes()).hexdigest() == digest


def test_recovery_module_never_writes_to_the_v1_artifact() -> None:
    source = (SCRIPTS / "availability_recovery.py").read_text(encoding="utf-8")
    for forbidden in ("write_text", "write_bytes", "open(", "unlink", "rename"):
        assert forbidden not in source, forbidden


def test_recovery_artifact_carries_explicit_linkage() -> None:
    art = recovery.build_recovery_artifact(
        original_path=SCREENING_V1,
        protocol_commit="c78c08fce81c5b96d21bb19d3b693d4c4c15feac",
        amendment_commit="abc1234",
        recovered_calls=[],
    )
    link = art["linkage"]
    assert link["protocol_commit"] == "c78c08fce81c5b96d21bb19d3b693d4c4c15feac"
    assert link["amendment_commit"] == "abc1234"
    assert link["original_artifact"] == "screening.json"
    assert link["original_artifact_sha256"] == hashlib.sha256(
        SCREENING_V1.read_bytes()
    ).hexdigest()
    assert art["amendment"] == "v1.1"
    assert "not evidence of visual or model incapability" in art["note"]


# --- the amendment changed nothing else ------------------------------------


def test_candidate_model_ids_unchanged() -> None:
    assert screen.CANDIDATE_MODELS == (
        "dots-studio/dots-3-note-preview:free",
        "google/gemma-4-26b-a4b-it:free",
        "google/gemma-4-31b-it:free",
    )
    assert "openrouter/free" in screen.FORBIDDEN_MODELS


def test_stimuli_digests_unchanged() -> None:
    doc = suite.build_suite()
    pinned = json.loads((ROOT / "benchmark" / "items.json").read_text(encoding="utf-8"))
    by_id = {i["item_id"]: i["image_sha256"] for i in pinned["items"]}
    for item in doc["items"]:
        assert item["image_sha256"] == by_id[item["item_id"]]


def test_scorer_and_sensory_boundary_untouched_by_the_amendment() -> None:
    scorer_src = (SCRIPTS / "score_handoff.py").read_text(encoding="utf-8")
    boundary_src = (ROOT / "ingress" / "openrouter_image.py").read_text(encoding="utf-8")
    # the amendment must not reach into scoring or perception
    assert "availability" not in scorer_src.lower()
    assert "availability" not in boundary_src.lower()
    assert "AlphaClaw's perception boundary" in boundary_src


def test_selection_hierarchy_text_unchanged() -> None:
    scorer = _load("score_handoff_amend", SCRIPTS / "score_handoff.py")
    for phrase in ("atomic-fact yield", "schema-compliance rate", "repeat stability",
                   "lowest mean output tokens", "lexicographically lowest"):
        assert phrase in scorer.SELECTION_RULE
