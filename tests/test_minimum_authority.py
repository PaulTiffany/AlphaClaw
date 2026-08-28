from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
CONTROLLER = ROOT / "controller"
INGRESS = ROOT / "ingress"
for path in (CONTROLLER, INGRESS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


inspector = _load("inspect_omega", CONTROLLER / "inspect_omega.py")
runner = _load("minimum_authority_omegaboi", CONTROLLER / "omegaboi.py")


def test_controller_is_separate_from_alpha_boundary() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    controller_readme = (CONTROLLER / "README.md").read_text(encoding="utf-8")

    assert "AlphaClaw is a small sensory tool" in readme
    assert "It is deliberately **not AlphaClaw**" in readme
    assert "This directory is **not AlphaClaw**" in controller_readme
    assert "perception != authority != inference" in controller_readme


def test_benchmark_does_not_carry_an_omega_source_transformer() -> None:
    assert not (CONTROLLER / "omega_profile.py").exists()
    source = (CONTROLLER / "omegaboi.py").read_text(encoding="utf-8")
    assert "apply_profile" not in source
    assert "shutil.copytree" not in source
    # The claim is measured against the pinned blobs, never asserted as a literal.
    # A hardcoded False reported an unmodified tree while the checkout carried
    # CRLF-rewritten bytes, so the constant form is now forbidden outright.
    assert 'omega_source_modified": False' not in source
    assert (
        '"omega_source_modified": not omega_pin.worktree_bytes_match_pin' in source
    )


def test_native_runtime_configuration_bounds_fresh_stock_container() -> None:
    contract = runner.EpisodeContract(max_reasoning_loops=3)
    command = runner._docker_run_command(
        image=runner.stock_image_tag(),
        container_name="fixture",
        proxy_url="http://host.docker.internal:9999/v1/",
        proxy_token="token",
        model="model",
        contract=contract,
        timeout=120,
        bounds_path=Path("/tmp/fixture/omega-bounds.yaml"),
    )

    # Bounds are still native Omega runtime configuration; they are supplied through
    # Omega's own config= file selector because argv overrides are untyped.
    assert f"config={runner.OMEGA_BOUNDS_CONTAINER_PATH}" in command
    assert contract.bounds_config(wakeup_interval=180) == {
        "maxNewInputLoops": 3,
        "maxWakeLoops": 0,
        "maxHistory": 0,
        "wakeupInterval": 180,
    }
    assert "provider=OpenAIAPI" in command
    assert "securityPolicyPath=/PeTTa/repos/OmegaClaw-Core/profile/policy.yaml" in command
    assert "--rm" in command
    assert "--security-opt" in command
    assert "no-new-privileges:true" in command


def test_inspector_reports_stock_state_without_certifying() -> None:
    report = inspector.inspect(ROOT / "OmegaClaw-Core")

    assert report["claim"] == "observed source state only; not a safety certificate or authorization"
    assert report["subject"]["sha"] == runner.OMEGA_SHA
    assert report["dynamic_command_registration_present"] is True
    assert report["dynamic_skill_surface_present"] is True
    assert report["persistent_history_writer_present"] is True
    json.dumps(report)


def test_recursive_self_improvement_cannot_self_authorize_authority_growth() -> None:
    philosophy = (ROOT / "PHILOSOPHY.md").read_text(encoding="utf-8")
    controller_source = (CONTROLLER / "omegaboi.py").read_text(encoding="utf-8")

    assert "## Capability is not permission" in philosophy
    assert "recursive proposal} \\neq \\text{recursive authorization" in philosophy
    assert "certified} \\neq \\text{authorized} \\neq \\text{worth doing" in philosophy
    assert "No high-consequence actuator without an independently authorized gate" in philosophy
    # The numeric bounds are declared by the episode contract and delivered to stock
    # Omega as a typed config file the controller mounts read-only.
    contract_source = (CONTROLLER / "episode_contract.py").read_text(encoding="utf-8")
    assert "maxNewInputLoops" in contract_source
    assert "maxWakeLoops" in contract_source
    assert "maxHistory" in contract_source
    assert "OMEGA_BOUNDS_CONTAINER_PATH" in controller_source
    assert "bounds_yaml" in controller_source


def test_chad_philosophy_preserves_operator_slack_and_fallibility() -> None:
    philosophy = (ROOT / "PHILOSOPHY.md").read_text(encoding="utf-8")

    assert "## Leave room to be wrong" in philosophy
    assert "Do not bite off more than you can chew." in philosophy
    assert "Do not make yourself the only thing holding the work together." in philosophy
    assert "Take care of the operator." in philosophy
    assert "recoverable progress" in philosophy
    assert "## This philosophy may also be wrong" in philosophy
    assert "Do not defend something merely because it is yours." in philosophy
