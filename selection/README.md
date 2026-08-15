# OmegaClaw inference selection

This directory is the discovery layer between the mechanically witnessed OmegaClaw residency
contract and actual model qualification.

It answers:

> What inference models can stock OmegaClaw address through its existing provider surface, and
> what facts does the provider currently advertise about them?

It does **not** answer:

> Which model is good enough to be OmegaClaw's resident inference?

That second question requires behavioral qualification against `certification/`.

## Default cost policy: cheapest paid candidate

Free OpenRouter routes remain useful for experiments, but AlphaClaw does not treat them as the
default resident inference path. Free variants can have materially different rate limits and
availability, which is a bad fit for OmegaClaw's repeated agent loop.

The live census therefore asks OpenRouter to return models using its server-side
`pricing-low-to-high` order, then mechanically:

1. keeps models compatible with stock OmegaClaw's text-in/text-out OpenRouter transport;
2. excludes zero-price / `:free` routes from the default resident policy;
3. excludes dynamic routers such as `openrouter/free` and `openrouter/auto` so model identity is
   fixed;
4. applies any explicit context or metadata-signal filters;
5. emits the first surviving model as `cheapest_paid_candidate`.

AlphaClaw deliberately preserves OpenRouter's price ordering rather than inventing a local blended
price formula.

**Important:** `cheapest_paid_candidate` is still only a metadata candidate. It remains
`unqualified` until a behavioral qualification harness demonstrates the powers in the OmegaClaw
Residency Certificate. The eventual selection rule is therefore:

> cheapest paid model among models mechanically qualified for this OmegaClaw residency contract.

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
- OpenRouter's provider-side price rank;
- context length;
- input/output modalities;
- advertised supported parameters such as `tools`, `reasoning`, and structured output controls;
- pricing and explicit `:free` status;
- provider/request-limit metadata;
- whether the catalog metadata is compatible with stock OmegaClaw's text-in/text-out OpenRouter
  transport.

Every model remains `unqualified` until a later behavioral test demonstrates the powers in the
OmegaClaw Residency Certificate.

## Live paid census

```bash
export OPENROUTER_API_KEY=...
python selection/openrouter_models.py \
  --omega-source OmegaClaw-Core \
  --output /tmp/openrouter-models.json \
  --paid-only \
  --require-paid-candidate
```

Never commit an API key. The GitHub workflow reads it from the repository secret
`OPENROUTER_API_KEY`.

Free routes can still be inventoried explicitly:

```bash
python selection/openrouter_models.py \
  --omega-source OmegaClaw-Core \
  --output /tmp/free-reasoning.json \
  --free-only \
  --require-signal reasoning
```

Metadata signals narrow the census; they do not constitute residency qualification. In particular,
OmegaClaw does not intrinsically require API-native function calling, so `tools=true` is evidence
about a model, not a base admission rule.

## Offline/replay mode

A previously captured OpenRouter response can be replayed without network access:

```bash
python selection/openrouter_models.py \
  --omega-source OmegaClaw-Core \
  --input raw-openrouter-models.json \
  --output /tmp/replayed-census.json \
  --paid-only
```

That makes normalization and selection logic testable without spending inference or depending on
live provider state.
