from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _load_health():
    path = ROOT / "runtime" / "huggingface" / "health.py"
    spec = importlib.util.spec_from_file_location("alphaclaw_hf_health", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hf_health_routes_ignore_ui_query_parameters() -> None:
    health = _load_health()
    assert health.route_path("/") == "/"
    assert health.route_path("/?__theme=dark") == "/"
    assert health.route_path("/health?probe=1") == "/health"
    assert health.route_path("/missing?probe=1") == "/missing"
