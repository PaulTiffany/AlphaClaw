from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_omegaclaw_is_a_real_upstream_submodule() -> None:
    modules = read(".gitmodules")
    assert 'submodule "OmegaClaw-Core"' in modules
    assert "https://github.com/asi-alliance/OmegaClaw-Core.git" in modules

    mode, indexed_sha, _stage, path = subprocess.check_output(
        ["git", "ls-files", "-s", "OmegaClaw-Core"], cwd=ROOT, text=True
    ).strip().split()
    assert mode == "160000"
    assert path == "OmegaClaw-Core"

    checked_out_sha = subprocess.check_output(
        ["git", "-C", "OmegaClaw-Core", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    assert checked_out_sha == indexed_sha


def test_upstream_submodule_is_pristine() -> None:
    status = subprocess.check_output(
        ["git", "-C", "OmegaClaw-Core", "status", "--porcelain"], cwd=ROOT, text=True
    )
    assert status == ""


def test_runner_composes_stock_omegaclaw_with_alpha_overlay() -> None:
    runner = read("run.metta")
    assert "(library OmegaClaw-Core lib_omegaclaw)" in runner
    assert "(library AlphaClaw alphaclaw)" in runner
    assert "!(omegaclaw)" in runner


def test_inference_contract_is_first_class_context() -> None:
    overlay = read("alphaclaw.metta")
    required = [
        "ALPHACLAW INFERENCE CONTRACT",
        "resident_provider:",
        "resident_model:",
        "resident_modalities:",
        "multimodal_capability: ingress-only",
        "symbolic_target:",
        "nontext_output: tool-mediated-actuation",
        "effectors:",
        "AGENCY HORIZON:",
        "cycles_per_new_human_input:",
        "scheduled_wake_cycles:",
        "prompt-extension alphaclaw-inference-contract",
    ]
    for phrase in required:
        assert phrase in overlay


def test_policy_makes_ingress_one_call_and_fixed() -> None:
    overlay = read("alphaclaw.metta")
    assert "Treat resident inference and ingress inference as different capabilities." in overlay
    assert "uses the configured multimodal capability once" in overlay
    assert "symbolic handoff as fixed input evidence" in overlay
    assert "Continue the reasoning trajectory on the fixed symbolic/text representation" in overlay
    assert "Do not re-query ingress inference from inside the resident loop" in overlay
    assert "ask for a new human-mediated ingress" in overlay
    assert "Never infer resident capabilities from the model brand" in overlay


def test_policy_exposes_mechanical_finite_horizon_without_second_counter() -> None:
    overlay = read("alphaclaw.metta")
    assert "configGetByKey maxNewInputLoops 50" in overlay
    assert "configGetByKey maxWakeLoops 1" in overlay
    assert "mechanically governs this resident" in overlay
    assert "AlphaClaw grants no extra cycles" in overlay
    assert "Plan within the finite horizon" in overlay
    assert "wait for new human input" in overlay


def test_policy_separates_intent_actuation_and_receipts() -> None:
    overlay = read("alphaclaw.metta")
    required = [
        "Treat cognition, intent, actuation, and evidence of actuation as distinct stages.",
        "use configured OmegaClaw tools or skills as effectors",
        "generated media as an artifact produced by an effector invocation",
        "Preserve an actuation receipt whenever the tool surface exposes one",
        "must not be the sole certifier of its own actuation",
        "embodiment/signposting are effects for observers to perceive",
    ]
    for phrase in required:
        assert phrase in overlay


def test_legacy_mini_agent_framework_is_gone() -> None:
    assert not (ROOT / "src" / "alphaclaw").exists()


def test_metta_overlay_parentheses_are_balanced() -> None:
    text = read("alphaclaw.metta")
    depth = 0
    in_string = False
    escaped = False
    for char in text:
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_string:
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            assert depth >= 0
    assert not in_string
    assert depth == 0
