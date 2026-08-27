from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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


runner = _load("omegaboi", CONTROLLER / "omegaboi.py")


def test_benchmark_dependencies_are_exact_clean_gitlinks() -> None:
    assert runner.verify_omega() == runner.OMEGA_SHA
    assert runner.verify_threadkeeper() == runner.THREADKEEPER_SHA


def test_docker_command_runs_stock_omega_with_runtime_configuration_only() -> None:
    contract = runner.EpisodeContract(max_reasoning_loops=7)
    command = runner._docker_run_command(
        image=runner.stock_image_tag(),
        container_name="omegaboi-test",
        proxy_url="http://host.docker.internal:12345/v1/",
        proxy_token="fixture-token",
        model="asi1-ultra",
        contract=contract,
        timeout=90,
    )

    assert "TEST_SERVER_IP=host.docker.internal" in command
    assert "OPENAIAPI_API_KEY=fixture-token" in command
    assert "provider=OpenAIAPI" in command
    assert "openaiapi_url=http://host.docker.internal:12345/v1/" in command
    assert "model=asi1-ultra" in command
    assert "maxNewInputLoops=7" in command
    assert "maxWakeLoops=0" in command
    assert "maxHistory=0" in command
    assert "wakeupInterval=150" in command
    assert "securityPolicyPath=/PeTTa/repos/OmegaClaw-Core/profile/policy.yaml" in command
    assert "-v" not in command
    assert "--volume" not in command


def test_stock_image_tag_is_bound_to_pinned_omega_sha() -> None:
    assert runner.OMEGA_SHA[:12] in runner.stock_image_tag()
    assert "stock" in runner.stock_image_tag()


def test_usage_summary_counts_threadkeeper_records(tmp_path: Path) -> None:
    usage = tmp_path / "usage.jsonl"
    usage.write_text(
        "\n".join(
            [
                json.dumps({"input_tokens": 10, "output_tokens": 2}),
                json.dumps({"input_tokens": 20, "output_tokens": 3}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert runner.usage_summary(usage) == {
        "calls": 2,
        "input_tokens": 30,
        "output_tokens": 5,
    }


def test_alpha_ingress_does_not_import_threadkeeper() -> None:
    for path in (ROOT / "ingress").glob("*.py"):
        assert "ThreadKeeper" not in path.read_text(encoding="utf-8")
        assert "threadkeeper" not in path.read_text(encoding="utf-8")
