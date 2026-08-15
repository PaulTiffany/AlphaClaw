# OmegaClaw inference selection

This directory is the discovery layer between the mechanically witnessed OmegaClaw residency
contract and actual model qualification.

It answers:

> What inference models can stock OmegaClaw address through its existing provider surface, and
> what facts does the provider currently advertise about them?

It does **not** answer:

> Which model is good enough to be OmegaClaw's resident inference?

That second question requires behavioral qualification against `certification/`.

## OpenRouter census

`openrouter_models.py` pulls OpenRouter's `/api/v1/models` catalog, normalizes the fields relevant
to OmegaClaw, and ties the result to the exact inspected OmegaClaw Git SHA.

Before accepting a catalog, it mechanically verifies the pinned OmegaClaw OpenRouter transport:

- a model can be selected through OmegaClaw's existing `model` override;
- the provider uses OpenRouter's OpenAI-compatible chat-completions endpoint;
- OmegaClaw consumes textual `message.content`;
- OmegaClaw sends an output-token bound.

Each catalog entry then records, without treating them as proof of competence:

- model id and canonical slug;
- context length;
- input/output modalities;
- advertised supported parameters such as `tools`, `reasoning`, and structured output controls;
- pricing and explicit `:free` status;
- provider/request-limit metadata;
- whether the catalog metadata is compatible with stock OmegaClaw's text-in/text-out OpenRouter
  transport.

Every model remains `unqualified` until a later behavioral test demonstrates the powers in the
OmegaClaw Residency Certificate.

## Run

```bash
export OPENROUTER_API_KEY=...
python selection/openrouter_models.py \
  --omega-source OmegaClaw-Core \
  --output /tmp/openrouter-models.json
```

Never commit an API key. The GitHub workflow reads it from the repository secret
`OPENROUTER_API_KEY`.

Useful metadata-only cuts are available:

```bash
python selection/openrouter_models.py \
  --omega-source OmegaClaw-Core \
  --output /tmp/free-reasoning.json \
  --free-only \
  --require-signal reasoning
```

These filters only narrow the census. They are not residency certification.

## Offline/replay mode

A previously captured OpenRouter response can be replayed without network access:

```bash
python selection/openrouter_models.py \
  --omega-source OmegaClaw-Core \
  --input raw-openrouter-models.json \
  --output /tmp/replayed-census.json
```

That makes normalization and selection logic testable without spending inference or depending on
live provider state.
