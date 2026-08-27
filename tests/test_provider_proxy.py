from __future__ import annotations

import importlib.util
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "controller"
if str(CONTROLLER) not in sys.path:
    sys.path.insert(0, str(CONTROLLER))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


proxy = _load("provider_proxy_test", CONTROLLER / "provider_proxy.py")
meter = _load("threadkeeper_meter_test", CONTROLLER / "threadkeeper_meter.py")


class FakeRecorder:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.run_id = "fake-run"
        self.raw_usage_log = run_dir / "provider_usage.jsonl"
        self.raw_usage_log.touch()
        self.rows: list[dict[str, object]] = []

    def record(self, **kwargs) -> None:
        self.rows.append(kwargs)


def _response(body):
    return {
        "id": "ok",
        "model": body["model"],
        "choices": [{"message": {"role": "assistant", "content": "(send hello)"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
    }


def test_gateway_preserves_stock_boot_then_bounds_post_handoff_calls(tmp_path: Path) -> None:
    recorder = FakeRecorder(tmp_path)

    def transport(spec, api_key, base_url, body):
        assert spec.display_name == "OpenRouter"
        assert api_key == "upstream-key"
        assert base_url == "https://example.invalid/v1"
        return _response(body)

    gateway = proxy.MeteredProviderGateway(
        upstream=proxy.UPSTREAMS["openrouter"],
        api_key="upstream-key",
        base_url="https://example.invalid/v1",
        model="demo-model",
        max_episode_calls=1,
        recorder=recorder,
        transport=transport,
    )

    gateway.handle_completion({"model": "demo-model", "messages": []})
    assert gateway.wait_for_boot_call(0.01)
    assert recorder.rows[0]["phase"] == "boot"

    gateway.mark_episode_started()
    gateway.release_episode_calls()
    gateway.handle_completion({"model": "demo-model", "messages": []})
    assert recorder.rows[1]["phase"] == "episode"

    blocked = gateway.handle_completion({"model": "demo-model", "messages": []})
    assert blocked["choices"][0]["message"]["content"] == "()"
    assert gateway.budget_exhausted is True
    assert len(recorder.rows) == 2

    raw = [json.loads(line) for line in recorder.raw_usage_log.read_text().splitlines()]
    assert [row["phase"] for row in raw] == ["boot", "episode"]
    assert raw[0]["usage"]["total_tokens"] == 12


def test_episode_request_waits_for_controller_release(tmp_path: Path) -> None:
    recorder = FakeRecorder(tmp_path)
    reached_upstream = threading.Event()
    result: list[dict[str, object]] = []

    def transport(spec, api_key, base_url, body):
        reached_upstream.set()
        return _response(body)

    gateway = proxy.MeteredProviderGateway(
        upstream=proxy.UPSTREAMS["asione"],
        api_key="key",
        base_url="https://example.invalid/v1",
        model="demo-model",
        max_episode_calls=2,
        recorder=recorder,
        transport=transport,
    )
    gateway.handle_completion({"model": "demo-model", "messages": []})
    reached_upstream.clear()
    gateway.mark_episode_started()

    thread = threading.Thread(
        target=lambda: result.append(
            gateway.handle_completion({"model": "demo-model", "messages": []})
        )
    )
    thread.start()
    thread.join(timeout=0.05)
    assert thread.is_alive()
    assert not reached_upstream.is_set()

    gateway.release_episode_calls()
    thread.join(timeout=1)
    assert not thread.is_alive()
    assert reached_upstream.is_set()
    assert result[0]["id"] == "ok"


def test_gateway_rejects_model_switch(tmp_path: Path) -> None:
    gateway = proxy.MeteredProviderGateway(
        upstream=proxy.UPSTREAMS["asione"],
        api_key="key",
        base_url="https://example.invalid/v1",
        model="expected",
        max_episode_calls=1,
        recorder=FakeRecorder(tmp_path),
        transport=lambda *args: {},
    )
    with pytest.raises(proxy.ProviderProxyError, match="unexpected model"):
        gateway.handle_completion({"model": "other"})


def test_raw_receipt_survives_threadkeeper_failure(tmp_path: Path) -> None:
    class FailingRecorder(FakeRecorder):
        def record(self, **kwargs) -> None:
            raise RuntimeError("witness failed")

    recorder = FailingRecorder(tmp_path)
    gateway = proxy.MeteredProviderGateway(
        upstream=proxy.UPSTREAMS["asione"],
        api_key="key",
        base_url="https://example.invalid/v1",
        model="demo-model",
        max_episode_calls=1,
        recorder=recorder,
        transport=lambda spec, api_key, base_url, body: _response(body),
    )

    with pytest.raises(RuntimeError, match="witness failed"):
        gateway.handle_completion({"model": "demo-model", "messages": []})

    raw = [json.loads(line) for line in recorder.raw_usage_log.read_text().splitlines()]
    assert len(raw) == 1
    assert raw[0]["phase"] == "boot"
    assert raw[0]["usage"]["prompt_tokens"] == 10


def test_threadkeeper_runs_isolated_and_receives_no_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASIONE_API_KEY", "do-not-cross")
    monkeypatch.setenv("OPENROUTER_API_KEY", "do-not-cross-either")

    assert meter.worker_command()[1] == "-I"
    worker_env = meter.sanitized_worker_env()
    assert "ASIONE_API_KEY" not in worker_env
    assert "OPENROUTER_API_KEY" not in worker_env

    recorder = meter.ThreadKeeperRecorder(run_dir=tmp_path, run_id="run-1")
    recorder.record(
        provider="ASIOne",
        model="asi1-ultra",
        phase="episode",
        response_payload={
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 4,
                "total_tokens": 15,
                "completion_tokens_details": {"reasoning_tokens": 2},
            }
        },
    )

    normalized = [json.loads(line) for line in (tmp_path / "usage.jsonl").read_text().splitlines()]
    assert normalized == [
        {
            "ts": normalized[0]["ts"],
            "thread_id": "run-1",
            "node_role": "omega_episode",
            "model": "asi1-ultra",
            "input_tokens": 11,
            "output_tokens": 4,
        }
    ]
    assert (tmp_path / "provider_usage.jsonl").read_text() == ""


def test_controller_never_imports_threadkeeper_into_its_interpreter() -> None:
    source = (CONTROLLER / "threadkeeper_meter.py").read_text(encoding="utf-8")
    assert "sys.path.insert" not in source
    assert "from threadkeeper_budget import" not in source
    assert "BudgetTracker(" not in source
