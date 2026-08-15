import importlib.util
from pathlib import Path

SOURCE = Path("qualification/asi_one_probe.py")
SPEC = importlib.util.spec_from_file_location("asi_one_probe", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_probe_record_preserves_model_usage_and_exact_marker():
    response = {
        "model": "asi1-mini",
        "choices": [{"message": {"content": "ALPHACLAW_ASI1_OK"}}],
        "usage": {
            "prompt_tokens": 11,
            "completion_tokens": 4,
            "total_tokens": 15,
        },
    }

    record = MODULE._probe_record(response)

    assert record["provider"] == "ASI:One"
    assert record["requested_model"] == "asi1-mini"
    assert record["resolved_model"] == "asi1-mini"
    assert record["marker_exact"] is True
    assert record["usage"]["total_tokens"] == 15
