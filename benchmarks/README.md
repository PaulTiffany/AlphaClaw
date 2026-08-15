# AlphaClaw benchmarks

This folder is a **lab**, not part of the AlphaClaw runtime.

AlphaClaw itself should stay flippantly small: stock OmegaClaw plus the Alpha inference contract. The benchmark layer exists only to ask whether that tiny architectural change buys anything.

## First experiment

Compare two clean runs on the same task set:

1. **Omega baseline** — stock OmegaClaw with multimodal inference resident in the reasoning loop.
2. **Alpha treatment** — the same pinned OmegaClaw core with `alphaclaw.metta`, a text-only resident model, and multimodal inference available only at ingress / as an explicit tool.

For each task, start from a clean memory state and keep the task, tools, loop limits, source evidence, and success criterion fixed. Model identity is an experimental variable and must be recorded explicitly.

## What to measure

Task success is primary. Cost is meaningful only conditional on comparable task success.

Record one JSON object per inference call in a JSONL trace:

```json
{"ts": 0.0, "thread_id": "task-001", "node_role": "resident", "model": "provider/model", "input_tokens": 1200, "output_tokens": 220}
{"ts": 1.0, "thread_id": "task-001", "node_role": "multimodal_ingress", "model": "provider/mm-model", "input_tokens": 900, "output_tokens": 180}
{"ts": 8.0, "thread_id": "task-001", "node_role": "multimodal_tool", "model": "provider/mm-model", "input_tokens": 400, "output_tokens": 80}
```

Useful `node_role` values are deliberately boring:

- `resident`
- `multimodal_ingress`
- `multimodal_tool`

The accounting format is intentionally compatible in spirit with Larry Greenblatt's **ThreadKeeper** `memory/usage.jsonl` seam: one record per LLM call, with model identity and input/output token counts. We reuse the measurement idea rather than importing ThreadKeeper's routing architecture into AlphaClaw.

ThreadKeeper: <https://github.com/hlgreenblatt/ThreadKeeper>

## Cost accounting

`analyze.py` aggregates calls and tokens and optionally applies an explicit model rate card. Rates are never baked into AlphaClaw because provider pricing changes.

```bash
python benchmarks/analyze.py \
  --baseline results/omega.jsonl \
  --alpha results/alpha.jsonl \
  --rates benchmarks/rates.example.json
```

The report distinguishes priced from unpriced calls so a missing rate cannot silently become a zero-dollar call.

## Hugging Face

`benchmarks/huggingface/` is a disposable analysis Space. It does **not** host a persistent agent and it does **not** make model calls. It only compares benchmark traces in a browser.

That keeps the governance boundary simple: the Space is a wind tunnel, not a resident agent.

## Evidence rule

Do not advertise a savings factor from a single illustrative run. Report the task set, model identities, pinned OmegaClaw SHA, success rate, multimodal call count, token totals, rate card used, and enough raw trace data for someone else to recompute the result.
