import importlib.util
from pathlib import Path

SOURCE = Path("qualification/build_task.py")
SPEC = importlib.util.spec_from_file_location("qualification_task", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_task_requires_policy_write_later_read_and_exact_completion():
    handoff = {
        "source": {"sha256": "a" * 64},
        "provenance": {"resolved_model": "example/vision"},
        "observation": {"literal": ["ALPHA CLAW", "FIXTURE 17"]},
    }
    task = MODULE.build_task(handoff, "REQ-17", "/tmp/result.json")
    assert "get-io-policy" in task
    assert "wait for the returned policy before writing" in task
    assert "later tool turn to read the file back" in task
    assert "QUALIFIED REQ-17" in task
    assert "/tmp/result.json" in task
