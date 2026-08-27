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


def test_threadkeeper_is_exact_clean_benchmark_gitlink() -> None:
    assert runner.verify_threadkeeper() == runner.THREADKEEPER_SHA


def test_docker_command_mounts_threadkeeper_read_only_and_selects_provider(tmp_path: Path) -> None:
    spec = runner.PROVIDERS["asione"]
    command = runner._docker_run_command(
        image="alphaclaw-omegaboi:test",
        container_name="omegaboi-test",
        output_dir=tmp_path,
        threadkeeper_dir=ROOT / "external" / "ThreadKeeper",
        provider=spec,
        model="asi1-ultra",
        openaiapi_url=None,
    )

    assert "TEST_SERVER_IP=host.docker.internal" in command
    assert any(value.endswith(":/ThreadKeeper:ro") for value in command)
    assert "provider=ASIOne" in command
    assert "model=asi1-ultra" in command
    assert "ASIONE_API_KEY" in command


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
