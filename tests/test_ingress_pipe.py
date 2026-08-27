from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INGRESS = ROOT / "ingress"
sys.path.insert(0, str(INGRESS))

SPEC = importlib.util.spec_from_file_location("alpha_pipe", INGRESS / "pipe.py")
PIPE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PIPE)


def test_text_passthrough_skips_sensory_inference_but_still_gets_prepend() -> None:
    def forbidden_image_runner(*_args, **_kwargs):
        raise AssertionError("text must not invoke multimodal inference")

    rendered, trace = PIPE.prepare(text="hello Omega", image_runner=forbidden_image_runner)
    document = json.loads(rendered)

    assert trace["route"] == PIPE.TEXT_PASSTHROUGH
    assert trace["sensory_inference"] is False
    assert document["kind"] == "alphaclaw_human_ingress"
    assert document["payload"]["content"] == "hello Omega"
    assert any("fixed text-only evidence" in line for line in document["contract"])
    assert any("Perceive multimedia only through" in line for line in document["contract"])


def test_utf8_text_file_passes_through_without_model(tmp_path: Path) -> None:
    source = tmp_path / "note.md"
    source.write_text("Only text here.", encoding="utf-8")

    def forbidden_image_runner(*_args, **_kwargs):
        raise AssertionError("text file must not invoke multimodal inference")

    rendered, trace = PIPE.prepare(input_file=source, image_runner=forbidden_image_runner)
    document = json.loads(rendered)

    assert trace["route"] == PIPE.TEXT_PASSTHROUGH
    assert document["payload"]["content"] == "Only text here."


def test_image_uses_one_sensory_translation_then_gets_same_prepend(tmp_path: Path) -> None:
    source = tmp_path / "evidence.png"
    source.write_bytes(b"fake-png")
    calls: list[tuple[Path, str, str]] = []

    def fake_image_runner(path: Path, model: str, api_key: str):
        calls.append((path, model, api_key))
        return (
            {
                "schema_version": 1,
                "source": {"kind": "image", "filename": path.name},
                "observation": {"literal": ["VISIBLE TEXT"]},
                "provenance": {"provider": "fixture"},
            },
            {"node_role": "multimodal_ingress", "model": "fixture"},
        )

    rendered, trace = PIPE.prepare(
        input_file=source,
        model="fixture/model",
        api_key="fixture-key",
        image_runner=fake_image_runner,
    )
    document = json.loads(rendered)
    handoff = json.loads(document["payload"]["content"])

    assert calls == [(source, "fixture/model", "fixture-key")]
    assert trace["route"] == PIPE.MULTIMODAL_INFERENCE
    assert trace["sensory_inference"] is True
    assert handoff["source"]["kind"] == "image"
    assert handoff["observation"]["literal"] == ["VISIBLE TEXT"]
    assert document["kind"] == "alphaclaw_human_ingress"
    assert any("text-only evidence" in line for line in document["contract"])


def test_image_requires_explicit_perception_credential(tmp_path: Path) -> None:
    source = tmp_path / "evidence.png"
    source.write_bytes(b"fake-png")

    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        PIPE.prepare(input_file=source, api_key="")


def test_unsupported_media_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "clip.bin"
    source.write_bytes(b"\x00\x01\x02")

    with pytest.raises(ValueError, match="unsupported ingress type"):
        PIPE.prepare(input_file=source)
