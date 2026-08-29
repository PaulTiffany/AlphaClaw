"""Research checkpoint -- offline index, verifier and documentation tests.

No network, no container, no provider call. These tests prove the checkpoint indexes the
real evidence, that the offline verifier is genuinely read-only and networkless, and that
the research summary quotes only numbers the synthesis modules derive.
"""

from __future__ import annotations

import ast
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

import research_checkpoint
import synthesis_v2
import synthesis_v3
import verify_research_checkpoint as verifier

MANIFEST = ROOT / "benchmark" / "research-checkpoint.json"
RESEARCH = ROOT / "RESEARCH.md"


@pytest.fixture(scope="module")
def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def research_text():
    return RESEARCH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def flat(research_text):
    return re.sub(r"\s+", " ", research_text.replace("*", "")).lower()


# --- the checkpoint indexes real evidence -------------------------------------


def test_every_checkpoint_digest_matches(manifest) -> None:
    for path, expected in manifest["evidence"].items():
        actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        assert actual == expected, path


def test_checkpoint_indexes_the_declared_evidence(manifest) -> None:
    declared = research_checkpoint.EVIDENCE
    assert set(manifest["evidence"]) == set(declared)
    assert len(declared) == len(set(declared))
    for path in declared:
        assert (ROOT / path).exists(), path


def test_checkpoint_covers_every_frozen_protocol_artifact(manifest) -> None:
    for required in ("benchmark/protocol-v2.json", "benchmark/screening-v2-B1.json",
                     "benchmark/benchmark-v2-A.json", "benchmark/benchmark-v2-B2.json",
                     "benchmark/benchmark-v2-C.json", "benchmark/protocol-v3.json",
                     "benchmark/benchmark-v3-A.json", "benchmark/benchmark-v3-B.json",
                     "benchmark/v3b-ground-truth.json", "scripts/score_handoff.py",
                     "scripts/synthesis_v2.py", "scripts/synthesis_v3.py"):
        assert required in manifest["evidence"], required


def test_checkpoint_regenerates_identically(manifest) -> None:
    assert research_checkpoint.build() == manifest


def test_checkpoint_restates_no_results(manifest) -> None:
    """It is an index. Results must be derived, not duplicated here."""
    assert manifest["restates_results"] is False
    blob = json.dumps(manifest)
    for banned in ("exact_match", "successful_episodes", "measured_cost_usd",
                   "avoidance_fraction", "transitions", "atomic_fact"):
        assert banned not in blob, banned
    numbers = re.findall(r"\b\d+\.\d+\b", blob)
    assert numbers == [], numbers


def test_substrate_is_read_from_committed_evidence(manifest) -> None:
    substrate = manifest["substrate"]
    assert substrate["omega_sha"] == "3d711e4b9f5254ae94f31123ca242f60cfd97d29"
    assert substrate["threadkeeper_sha"] == "a64de99e10f9f8078d25bff511b44fd71819e931"
    assert substrate["stock_omega_image_id"] == (
        "sha256:69ff11bf227b197f697aab4488e879258560730565838b19db25e3dd580af90a")
    assert substrate["pins_all_true"] is True
    assert research_checkpoint.substrate() == substrate


def test_checkpoint_records_the_synthesis_merges_and_base(manifest) -> None:
    assert manifest["synthesis_merge_commits"]["v2"] == \
        "364dac574464b1b39be9718a38a144a648b02976"
    assert manifest["synthesis_merge_commits"]["v3"] == \
        "5bb771df44809c731f1386a678c2cfe22f1e9d89"
    assert manifest["base_commit"] == "5bb771df44809c731f1386a678c2cfe22f1e9d89"
    assert manifest["protocols_complete"] == ["v2", "v3"]
    assert manifest["protocol_v4_started"] is False


# --- amendments ---------------------------------------------------------------


def test_all_four_amendments_are_recorded(manifest) -> None:
    ids = [a["id"] for a in manifest["amendments"]]
    assert ids == ["v2.1", "v2.2", "v3.1", "v3.2"]
    for amendment in manifest["amendments"]:
        assert (ROOT / amendment["module"]).exists(), amendment["id"]
        assert amendment["discovered"]
        assert amendment["changed"]
        assert amendment["unchanged"]
        assert "BEFORE" in amendment["relative_to_inference"], amendment["id"]


def test_amendment_chronology_appears_in_the_research_summary(flat) -> None:
    for token in ("v2.1", "v2.2", "v3.1", "v3.2"):
        assert token in flat, token
    assert "before" in flat
    assert "preregistration is what made them findable" in flat


# --- the offline verifier -----------------------------------------------------


def test_verifier_passes() -> None:
    summary = verifier.summary()
    assert summary["passed"] is True
    assert all(check["ok"] for check in summary["checks"])
    assert len(summary["checks"]) >= 15


def test_verifier_is_networkless_and_makes_no_provider_call() -> None:
    """No network module anywhere. ``subprocess`` is allowed only for local Git."""
    network = {"requests", "urllib", "socket", "http", "httpx", "ssl",
               "docker", "openrouter_image", "asyncio"}
    for name in ("verify_research_checkpoint.py", "research_checkpoint.py"):
        source = (SCRIPTS / name).read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not (imported & network), (name, sorted(imported & network))
        assert "http://" not in source and "https://" not in source, name
        assert "api_key" not in source.lower(), name
    assert "subprocess" not in (SCRIPTS / "research_checkpoint.py").read_text(
        encoding="utf-8")


def test_verifier_subprocess_use_is_read_only_local_git() -> None:
    """The only subprocess is `git`, from an allowlist, with no shell."""
    source = (SCRIPTS / "verify_research_checkpoint.py").read_text(encoding="utf-8")
    calls = [node for node in ast.walk(ast.parse(source))
             if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute)
             and isinstance(node.func.value, ast.Name)
             and node.func.value.id == "subprocess"]
    assert len(calls) == 1, "exactly one subprocess call expected"
    call = calls[0]
    assert call.func.attr == "run"
    keywords = {kw.arg for kw in call.keywords}
    assert "shell" not in keywords          # never a shell
    assert "capture_output" in keywords and "timeout" in keywords
    # the command list starts with the literal "git"
    first = call.args[0]
    assert isinstance(first, ast.List)
    assert isinstance(first.elts[0], ast.Constant) and first.elts[0].value == "git"

    for prefix in verifier.GIT_READ_ONLY_COMMANDS:
        assert prefix[0] in {"rev-parse", "cat-file", "merge-base"}, prefix
    for mutating in ("commit", "checkout", "push", "fetch", "clone", "reset",
                     "add", "tag"):
        assert not any(mutating in prefix for prefix in
                       verifier.GIT_READ_ONLY_COMMANDS), mutating


def test_verifier_refuses_a_non_allowlisted_git_command() -> None:
    with pytest.raises(ValueError, match="non-allowlisted"):
        verifier._git("push", "origin", "main")
    with pytest.raises(ValueError, match="non-allowlisted"):
        verifier._git("commit", "-m", "x")


def test_git_ancestry_facts_hold_in_this_checkout() -> None:
    checks = {c["name"]: c for c in verifier.summary()["checks"]}
    ancestry = [name for name in checks if "ancestor" in name]
    assert len(ancestry) == 3
    for name in ancestry:
        # inside a git checkout these must pass; outside they are skipped, never failed
        assert checks[name]["ok"] is True or checks[name]["skipped"] is True, name


def test_verifier_does_not_claim_git_proves_provider_call_chronology() -> None:
    source = (SCRIPTS / "verify_research_checkpoint.py").read_text(encoding="utf-8")
    assert "not the order of *provider calls*" in source
    assert "recorded process evidence" in source
    names = " ".join(c["name"] for c in verifier.summary()["checks"]).lower()
    assert "provider call" not in names       # no check claims call ordering


def test_verifier_has_no_write_path() -> None:
    source = (SCRIPTS / "verify_research_checkpoint.py").read_text(encoding="utf-8")
    for token in ("write_text", "write_bytes", "json.dump(", "unlink", "mkdir",
                  "shutil", "os.remove"):
        assert token not in source, token
    assert re.search(r"open\s*\([^)]*[\"']w", source) is None


def test_verifier_checks_the_things_that_matter() -> None:
    names = " ".join(check["name"] for check in verifier.summary()["checks"]).lower()
    for expected in ("artifact digests", "omegaclaw", "v2 synthesis", "v3 synthesis",
                     "no unique cause", "87.5%", "completed episodes",
                     "availability", "protocol v4"):
        assert expected in names, expected


# --- synthesis still reproduces ------------------------------------------------


def test_v2_synthesis_reproduces() -> None:
    assert all(synthesis_v2.artifact_digests_match().values())
    result = synthesis_v2.synthesis()
    assert result["B2"]["transitions"] == 0
    assert result["C"]["transitions"] == 3
    assert result["single_aggregate_accuracy_reported"] is False


def test_v3_synthesis_reproduces() -> None:
    assert all(synthesis_v3.artifact_digests_match().values())
    result = synthesis_v3.synthesis()
    assert result["V3A"]["unique_cause_isolated"] is False
    assert result["V3B_architecture"]["max_avoidance_fraction"] == pytest.approx(0.875)
    assert result["single_aggregate_v3_score_reported"] is False


# --- the research summary quotes only derived numbers -------------------------


def test_research_summary_headline_values_are_derived(research_text) -> None:
    v2 = synthesis_v2.synthesis()
    v3 = synthesis_v3.synthesis()
    section = re.sub(r"\s+", " ", research_text)

    assert f"{v2['B1']['atomic_facts_correct']}/{v2['B1']['atomic_facts_scoreable']}" \
        in section
    assert f"{v2['A']['text_control'][0]}/{v2['A']['text_control'][1]}" in section
    assert f"{v2['A']['image_text'][0]}/{v2['A']['image_text'][1]}" in section
    assert "0/3" in section and "3/3" in section

    for fraction in ("0%", "50%", "75%", "87.5%"):
        assert fraction in section, fraction
    for value in ("-2.7%", "+22.0%", "+38.0%", "+37.1%"):
        assert value in section, value

    availability = v3["V3B_availability"]
    assert str(availability["successes"]) in section
    assert str(availability["availability_failures"]) in section


def test_research_summary_carries_the_claims_table(flat) -> None:
    for supported in ("sensory substitution caused 0/3 paired transitions",
                      "resident substitution caused 3/3 transitions",
                      "v3-a did not isolate a unique cause",
                      "perceive-once reduced multimodal calls according to depth"):
        assert supported in flat, supported
    for non_claim in ("any universal model ranking",
                      "a universal break-even at n=2",
                      "that alphaclaw is always cheaper",
                      "that alphaclaw is always more accurate",
                      "that qwen pricing generalises to other providers",
                      "that all perceive-once architectures show the same economics"):
        assert non_claim in flat, non_claim


def test_research_summary_avoids_inflation_and_unnecessary_pessimism(flat) -> None:
    assert "mixed results" not in flat
    assert "not evidence of architecture instability" in flat
    for banned in ("alphaclaw score", "overall score", "aggregate score"):
        assert banned not in flat, banned


def test_research_summary_has_the_text_architecture_diagram(research_text) -> None:
    assert "multimodal sensory inference  (once)" in research_text
    assert "symbolic handoff" in research_text
    assert "text resident turn 1" in research_text
    assert "image + state  -> multimodal turn 2" in research_text
    assert ".png" not in research_text.split("## Architecture")[1].split("---")[0]


def test_research_summary_separates_the_two_reproduction_paths(flat) -> None:
    assert "reproduce the published analysis" in flat
    assert "no api key" in flat
    assert "re-run the experiments" in flat
    assert "requires credentials and costs money" in flat
    assert "without trusting current provider availability" in flat


def test_availability_failures_stay_availability(flat) -> None:
    assert "0 wrong answers" in flat
    assert "4 upstream availability failures" in flat


# --- nothing frozen moved ------------------------------------------------------


def test_no_frozen_result_artifact_modified(manifest) -> None:
    for name, expected in (
            ("benchmark-v2-A.json",
             "644f36e406df5520f54e6bcb706b891e9dd1ff9094c6c0d59cfb305e68be65ea"),
            ("benchmark-v2-B2.json",
             "8b6cc4557b27c8cc2acf7803ca05293b0fd39ca1fe1cc6f89dbe838045fd7d48"),
            ("benchmark-v2-C.json",
             "b46ea2ceb4429c15bd3fa5b422d4e47e5a3acdb70467b6c5a3960eee090f6c88"),
            ("benchmark-v3-A.json",
             "98ab018e8f8dcb2de405e21a800239583968c7832b1a8665cd31686072ad6552"),
            ("benchmark-v3-B.json",
             "f5ddcf3d77f010a4d199d6eea4c87fa093b3fe7576d01258a9997b9b493aeab2")):
        actual = hashlib.sha256(
            (ROOT / "benchmark" / name).read_bytes()).hexdigest()
        assert actual == expected == manifest["evidence"][f"benchmark/{name}"], name


def test_scorer_untouched() -> None:
    scorer = (SCRIPTS / "score_handoff.py").read_text(encoding="utf-8")
    assert "is located to the left of" not in scorer
    assert hashlib.sha256(scorer.encode("utf-8")).hexdigest() == (
        "54fca8997f1f0dea9555b5b91f145d477c8b3172b4bc09a590b35454f6191699")


def test_documented_install_command_matches_ci() -> None:
    """Docs must not drift from the versions CI actually installs."""
    match = None
    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        match = re.search(r"pip install (pytest==\S+) (ruff==\S+)",
                          workflow.read_text(encoding="utf-8"))
        if match:
            break
    assert match, "CI install line not found in any workflow"
    research = RESEARCH.read_text(encoding="utf-8")
    assert match.group(1) in research, match.group(1)
    assert match.group(2) in research, match.group(2)


def test_documented_verifier_command_exists() -> None:
    research = RESEARCH.read_text(encoding="utf-8")
    assert "python scripts/verify_research_checkpoint.py" in research
    assert (SCRIPTS / "verify_research_checkpoint.py").exists()


def test_research_summary_separates_verified_from_recorded(flat) -> None:
    """The distinction the checkpoint depends on must be stated, not implied."""
    assert "what is mechanically checked, and what is recorded" in flat
    assert "recorded in the repository history" in flat
    assert "order of commits, not the order of provider calls" in flat
    assert "skipped rather than failed outside a git checkout" in flat


def test_absent_commits_skip_rather_than_fail(manifest) -> None:
    """CI clones shallowly: a commit missing from the checkout is unknown, not false.

    Regression guard -- treating absence as failure broke CI while passing locally.
    """
    absent = "0" * 40
    fake = {**manifest, "base_commit": absent,
            "synthesis_merge_commits": {"v2": absent, "v3": absent}}
    results: list = []
    verifier.git_ancestry(fake, results)
    assert len(results) == 3, "every ancestry check must be emitted, never dropped"
    assert all(ok is verifier.SKIPPED for _name, ok, _detail in results)
    assert all("not in this checkout" in detail for _n, _o, detail in results)


def test_a_present_but_wrong_ancestry_still_fails(manifest) -> None:
    """Skipping absent commits must not soften a real contradiction."""
    head_only = {**manifest,
                 "base_commit": manifest["base_commit"],
                 "synthesis_merge_commits": manifest["synthesis_merge_commits"]}
    results: list = []
    verifier.git_ancestry(head_only, results)
    if any(ok is verifier.SKIPPED for _n, ok, _d in results):
        pytest.skip("shallow checkout: ancestry not consultable here")
    assert all(ok is True for _n, ok, _d in results)
