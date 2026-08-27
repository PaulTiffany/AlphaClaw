import importlib.util
from pathlib import Path

import pytest

SOURCE = Path("ingress/openrouter_image.py")
SPEC = importlib.util.spec_from_file_location("openrouter_image", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_json_from_markdown_fence():
    payload = MODULE._json_from_text('```json\n{"literal_observations": []}\n```')
    assert payload == {"literal_observations": []}


def test_normalize_handoff_keeps_observation_separate_from_interpretation(tmp_path):
    image = tmp_path / "fixture.png"
    image.write_bytes(b"fake-image")
    payload = {
        "literal_observations": ["ALPHA CLAW"],
        "interpretations": ["A project logo"],
        "uncertainty": ["Species styling is illustrative"],
        "unresolved": [],
        "entities": [{"label": "ALPHA CLAW", "kind": "visible text"}],
        "relations": [
            {"subject": "PERCEIVE", "predicate": "precedes", "object": "SYMBOLIZE"}
        ],
    }
    handoff = MODULE.normalize_handoff(
        payload,
        image=image,
        mime_type="image/png",
        requested_model="openrouter/free",
        resolved_model="example/vision:free",
    )
    assert handoff["observation"]["literal"] == ["ALPHA CLAW"]
    assert handoff["observation"]["interpretations"] == ["A project logo"]
    assert handoff["provenance"]["resolved_model"] == "example/vision:free"
    assert len(handoff["source"]["sha256"]) == 64


def test_build_request_asks_openrouter_for_usage(tmp_path):
    image = tmp_path / "fixture.png"
    image.write_bytes(b"fake-image")
    payload, _mime_type = MODULE.build_request(image, "openrouter/free")
    assert payload["usage"] == {"include": True}


def test_response_content_rejects_unknown_usage():
    response = {
        "model": "example/vision:free",
        "choices": [{"message": {"content": "{}"}}],
    }
    with pytest.raises(TypeError, match="did not include usage accounting"):
        MODULE.response_content(response)


def test_trace_uses_existing_benchmark_role():
    row = MODULE.trace_record(
        requested_model="openrouter/free",
        resolved_model="example/vision:free",
        input_tokens=123,
        output_tokens=45,
        source_sha256="a" * 64,
    )
    assert row["node_role"] == "multimodal_ingress"
    assert row["model"] == "example/vision:free"
    assert row["input_tokens"] == 123
    assert row["output_tokens"] == 45
