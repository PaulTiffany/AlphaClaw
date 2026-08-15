import importlib.util
from pathlib import Path

SOURCE = Path("selection/openrouter_models.py")
SPEC = importlib.util.spec_from_file_location("openrouter_models", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

build_census = MODULE.build_census
normalize_model = MODULE.normalize_model
witness_omega_openrouter = MODULE.witness_omega_openrouter


def test_normalize_model_preserves_metadata_without_claiming_qualification():
    model = normalize_model(
        {
            "id": "example/reasoner:free",
            "canonical_slug": "example/reasoner",
            "name": "Reasoner",
            "context_length": 131072,
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["text"],
                "tokenizer": "Example",
                "instruct_type": "chatml",
            },
            "supported_parameters": ["tools", "reasoning", "max_tokens"],
            "pricing": {
                "prompt": "0",
                "completion": "0",
                "request": "0",
                "internal_reasoning": "0",
            },
        }
    )

    assert model["stock_omega_openrouter_addressable"] is True
    assert model["explicit_free_variant"] is True
    assert model["zero_text_price"] is True
    assert model["signals"]["tools"] is True
    assert model["signals"]["reasoning"] is True
    assert model["qualification"]["status"] == "unqualified"


def test_non_text_input_is_not_stock_omega_addressable():
    model = normalize_model(
        {
            "id": "example/image-only",
            "architecture": {
                "input_modalities": ["image"],
                "output_modalities": ["text"],
            },
            "supported_parameters": [],
            "pricing": {"prompt": "0", "completion": "0"},
        }
    )

    assert model["stock_omega_openrouter_addressable"] is False


def test_build_census_filters_metadata_but_does_not_certify_models():
    payload = {
        "data": [
            {
                "id": "example/free-reasoner:free",
                "context_length": 100000,
                "architecture": {
                    "input_modalities": ["text"],
                    "output_modalities": ["text"],
                },
                "supported_parameters": ["reasoning", "max_tokens"],
                "pricing": {"prompt": "0", "completion": "0"},
            },
            {
                "id": "example/paid",
                "context_length": 200000,
                "architecture": {
                    "input_modalities": ["text"],
                    "output_modalities": ["text"],
                },
                "supported_parameters": ["reasoning", "max_tokens"],
                "pricing": {"prompt": "0.000001", "completion": "0.000002"},
            },
        ]
    }

    census = build_census(
        payload,
        omega_source=Path("OmegaClaw-Core"),
        source_url="fixture",
        free_only=True,
        min_context=65536,
        require_signals=["reasoning"],
    )

    assert census["counts"]["models"] == 1
    assert census["models"][0]["id"] == "example/free-reasoner:free"
    assert census["models"][0]["qualification"]["status"] == "unqualified"


def test_pinned_omega_openrouter_transport_is_witnessed():
    witness = witness_omega_openrouter(Path("OmegaClaw-Core"))

    assert witness["provider"] == "OpenRouter"
    assert witness["transport"] == "openai-compatible-chat-completions"
    assert witness["resident_io"] == "text-in/text-out"
    assert len(witness["sha"]) == 40
