import importlib.util
import sys
from pathlib import Path

SOURCE = Path("qualification/run_omega_residency.py")
sys.path.insert(0, str(SOURCE.parent))
SPEC = importlib.util.spec_from_file_location("omega_residency_runner", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_residency_handoff_is_deterministic_and_model_bound() -> None:
    first = MODULE.make_handoff("asi1-mini")
    second = MODULE.make_handoff("asi1-mini")

    assert first == second
    assert first["source"]["kind"] == "deterministic-residency-fixture"
    assert first["source"]["sha256"]
    assert first["provenance"] == {
        "provider": "ASIOne",
        "resolved_model": "asi1-mini",
    }
    assert len(first["literal_observations"]) == 3
    assert MODULE.FIXTURE_TEXT.endswith("\n")


def test_sponsor_handoff_is_provider_bound() -> None:
    handoff = MODULE.make_handoff("minimax/minimax-m3", "ASICloud")
    assert handoff["provenance"] == {
        "provider": "ASICloud",
        "resolved_model": "minimax/minimax-m3",
    }


def test_provider_credentials_are_explicit_and_minimal() -> None:
    assert MODULE.provider_config("ASIOne") == {
        "canonical_key_env": "ASI_ONE_API_KEY",
        "stock_key_env": "ASIONE_API_KEY",
        "default_model": "asi1-mini",
    }
    assert MODULE.provider_config("ASICloud") == {
        "canonical_key_env": "ASI_API_KEY",
        "stock_key_env": "ASI_API_KEY",
        "default_model": "minimax/minimax-m3",
    }


def test_expected_file_is_exactly_the_qualification_contract() -> None:
    handoff = MODULE.make_handoff("asi1-mini")

    assert MODULE.expected_file(handoff, "RUN-17") == {
        "marker": "RUN-17",
        "source_sha256": handoff["source"]["sha256"],
        "resolved_model": "asi1-mini",
        "literal_count": 3,
    }


def test_call_counter_uses_upstream_chars_sent_witness() -> None:
    logs = "noise\nCHARS_SENT: 123\nmore\nCHARS_SENT: 9\n"
    assert MODULE.count_llm_calls(logs) == 2


def test_redaction_removes_canonical_and_stock_secret_values() -> None:
    assert MODULE.redact("a=secret b=bridge", ["secret", "bridge"]) == "a=*** b=***"
