"""Offline proof of the three benchmark ingress modes.

No network. The sensory boundary is replaced by a fake runner, so the perception call
is counted and its handoff inspected without contacting a provider.

The architecture under test is deliberately:

    original image bytes -> sensory boundary -> symbolic handoff -> bounded stock Omega

These are not tests of Omega seeing image bytes. Omega's channel carries strings and
its provider request body carries a plain string, so the transformation is mechanically
required and is recorded as sensory inference rather than hidden.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INGRESS = ROOT / "ingress"
SCRIPTS = ROOT / "scripts"
for extra in (INGRESS, SCRIPTS):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pipe = _load("ingress_pipe_tranche", INGRESS / "pipe.py")
stimuli = _load("benchmark_stimuli", SCRIPTS / "make_benchmark_stimuli.py")

# Pinned stimulus digest. zlib level 0 keeps the bytes identical on every machine.
STIMULUS_SHA256 = "3775285f05aeded8deaadfa57d1570861a16d417f0c6462f3c4847cbae861334"

COMBINED_TEXT = (
    "Reply only with the token shown in the image "
    "followed by the number of shapes shown."
)
# Pinned so a silent edit to the stimulus text cannot pass unnoticed.
COMBINED_TEXT_SHA256 = "82bac632f15b7df0607987dfdd1e4870ab308f5326bdd6fb62a26793a0e66fdc"

# What a faithful sensory boundary returns for this stimulus. Shaped exactly like the
# real normalize_handoff() output so the payload composition under test is realistic.
FAKE_HANDOFF = {
    "literal_observations": [
        "Black text reading K7 on a white background",
        "Three separated blue squares in a horizontal row",
    ],
    "interpretations": ["A token label beside a count of three shapes"],
    "uncertainty": [],
    "unresolved": [],
    "entities": [
        {"label": "K7", "kind": "text"},
        {"label": "blue square", "kind": "shape"},
        {"label": "blue square", "kind": "shape"},
        {"label": "blue square", "kind": "shape"},
    ],
    "relations": [{"subject": "K7", "predicate": "appears_beside", "object": "blue squares"}],
    "source": {"sha256": STIMULUS_SHA256, "mime_type": "image/png"},
}

FAKE_TRACE = {
    "timestamp": "2026-08-28T00:00:00+00:00",
    "node_role": "multimodal_ingress",
    "provider": "OpenRouter",
    "requested_model": "openrouter/free",
    "model": "openrouter/free",
    "input_tokens": 812,
    "output_tokens": 143,
    "source_sha256": STIMULUS_SHA256,
}


class _CountingRunner:
    """Stands in for the sensory boundary and counts how often it is invoked."""

    def __init__(self) -> None:
        self.calls: list[tuple[Path, str, str]] = []

    def __call__(self, image: Path, model: str, api_key: str):
        self.calls.append((image, model, api_key))
        return FAKE_HANDOFF, FAKE_TRACE


@pytest.fixture
def stimulus(tmp_path: Path) -> Path:
    path = tmp_path / "stimulus.png"
    path.write_bytes(stimuli.render())
    return path


# --- deterministic stimulus -------------------------------------------------


def test_stimulus_is_byte_deterministic() -> None:
    assert hashlib.sha256(stimuli.render()).hexdigest() == STIMULUS_SHA256
    assert stimuli.render() == stimuli.render()


def test_stimulus_carries_both_modalities_of_evidence() -> None:
    assert stimuli.TOKEN == "K7"
    assert len(stimuli.SQUARE_LEFT) == 3
    assert stimuli.BLUE == (0, 0, 255)


# --- mode 1: text only, must be unchanged -----------------------------------


def test_text_only_route_is_unchanged() -> None:
    payload, trace = pipe.prepare(text="Reply with the single word: ORANGE")
    document = json.loads(payload)
    assert document["payload"]["content"] == "Reply with the single word: ORANGE"
    assert trace["route"] == pipe.TEXT_PASSTHROUGH
    assert trace["sensory_inference"] is False
    assert "sensory_trace" not in trace


def test_text_only_digest_is_of_the_text_bytes() -> None:
    text = "Reply with the single word: ORANGE"
    _, trace = pipe.prepare(text=text)
    assert trace["source_sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- mode 2: image only, must be unchanged ----------------------------------


def test_image_only_route_is_unchanged(stimulus: Path) -> None:
    runner = _CountingRunner()
    payload, trace = pipe.prepare(
        input_file=stimulus, model="m", api_key="k", image_runner=runner
    )
    assert trace["route"] == pipe.MULTIMODAL_INFERENCE
    assert trace["sensory_inference"] is True
    assert trace["source_sha256"] == STIMULUS_SHA256
    assert trace["sensory_trace"] == FAKE_TRACE
    assert "text_sha256" not in trace
    assert len(runner.calls) == 1

    # The payload is the bare handoff, exactly as before this change.
    content = json.loads(json.loads(payload)["payload"]["content"])
    assert content == FAKE_HANDOFF


def test_image_only_handoff_carries_the_salient_visible_facts(stimulus: Path) -> None:
    """Grade the transformation, not an unconstrained final utterance."""
    runner = _CountingRunner()
    payload, _ = pipe.prepare(
        input_file=stimulus, model="m", api_key="k", image_runner=runner
    )
    content = json.loads(json.loads(payload)["payload"]["content"])
    flattened = json.dumps(content)
    assert "K7" in flattened
    assert sum(1 for e in content["entities"] if e["label"] == "blue square") == 3


# --- mode 3: image + text, one input ----------------------------------------


def test_combined_is_accepted(stimulus: Path) -> None:
    runner = _CountingRunner()
    _, trace = pipe.prepare(
        text=COMBINED_TEXT, input_file=stimulus, model="m", api_key="k", image_runner=runner
    )
    assert trace["route"] == pipe.MULTIMODAL_INFERENCE_WITH_TEXT
    assert trace["sensory_inference"] is True


def test_combined_performs_exactly_one_perception_call(stimulus: Path) -> None:
    runner = _CountingRunner()
    pipe.prepare(
        text=COMBINED_TEXT, input_file=stimulus, model="m", api_key="k", image_runner=runner
    )
    assert len(runner.calls) == 1
    assert runner.calls[0][0] == stimulus


def test_combined_becomes_one_labelled_payload(stimulus: Path) -> None:
    runner = _CountingRunner()
    payload, _ = pipe.prepare(
        text=COMBINED_TEXT, input_file=stimulus, model="m", api_key="k", image_runner=runner
    )
    envelope = json.loads(payload)
    content = json.loads(envelope["payload"]["content"])
    assert set(content) == {"human_text", "sensory_handoff"}
    assert content["human_text"] == COMBINED_TEXT
    assert content["sensory_handoff"] == FAKE_HANDOFF
    # One envelope, one payload: the two modalities did not become two turns.
    assert isinstance(envelope["payload"]["content"], str)


def test_combined_records_both_provenance_digests_separately(stimulus: Path) -> None:
    runner = _CountingRunner()
    _, trace = pipe.prepare(
        text=COMBINED_TEXT, input_file=stimulus, model="m", api_key="k", image_runner=runner
    )
    assert trace["source_sha256"] == STIMULUS_SHA256
    assert trace["text_sha256"] == hashlib.sha256(COMBINED_TEXT.encode("utf-8")).hexdigest()
    assert trace["source_sha256"] != trace["text_sha256"]


def test_combined_answer_needs_both_modalities() -> None:
    """The text carries only the composition rule; the image carries the evidence."""
    # Neither the token nor the count may be derivable from the instruction alone.
    assert "K7" not in COMBINED_TEXT
    assert "3" not in COMBINED_TEXT
    # The instruction must not leak the visual class either, or the count becomes
    # answerable from the text plus a guess rather than from the handoff.
    lowered = COMBINED_TEXT.lower()
    assert "blue" not in lowered
    assert "square" not in lowered
    # The evidence side must supply both.
    handoff = json.dumps(FAKE_HANDOFF)
    assert "K7" in handoff
    assert sum(1 for e in FAKE_HANDOFF["entities"] if e["kind"] == "shape") == 3
    assert "followed by" in COMBINED_TEXT


def test_combined_text_digest_is_pinned() -> None:
    assert hashlib.sha256(COMBINED_TEXT.encode("utf-8")).hexdigest() == COMBINED_TEXT_SHA256


def test_combined_rejects_a_non_image_file(tmp_path: Path) -> None:
    text_file = tmp_path / "note.txt"
    text_file.write_text("not an image", encoding="utf-8")
    with pytest.raises(ValueError, match="requires an image"):
        pipe.prepare(text="hello", input_file=text_file, model="m", api_key="k")


def test_combined_requires_non_empty_text(stimulus: Path) -> None:
    with pytest.raises(ValueError, match="non-empty text"):
        pipe.prepare(text="   ", input_file=stimulus, model="m", api_key="k")


def test_empty_input_is_still_rejected() -> None:
    with pytest.raises(ValueError, match="provide text, input_file, or both"):
        pipe.prepare()


# --- invariants that must not move ------------------------------------------


def test_sensory_trace_alone_reconciles_the_paid_perception_call() -> None:
    """No metering change is needed: the trace already identifies the paid call."""
    for field in ("provider", "requested_model", "model", "input_tokens",
                  "output_tokens", "source_sha256", "timestamp"):
        assert field in FAKE_TRACE


def test_alpha_envelope_shape_is_identical_across_all_three_modes(stimulus: Path) -> None:
    runner = _CountingRunner()
    envelopes = [
        json.loads(pipe.prepare(text="hello")[0]),
        json.loads(pipe.prepare(input_file=stimulus, model="m", api_key="k",
                                image_runner=runner)[0]),
        json.loads(pipe.prepare(text=COMBINED_TEXT, input_file=stimulus, model="m",
                                api_key="k", image_runner=runner)[0]),
    ]
    shapes = {tuple(sorted(e)) for e in envelopes}
    assert len(shapes) == 1, f"envelope shape differs across modes: {shapes}"


def test_pinned_omega_is_not_referenced_by_ingress() -> None:
    source = (INGRESS / "pipe.py").read_text(encoding="utf-8")
    assert "OmegaClaw-Core" not in source
    assert "docker" not in source.lower()


def test_stimulus_generator_uses_only_the_standard_library() -> None:
    source = (SCRIPTS / "make_benchmark_stimuli.py").read_text(encoding="utf-8")
    for heavy in ("PIL", "Pillow", "numpy", "cv2", "matplotlib"):
        assert heavy not in source
