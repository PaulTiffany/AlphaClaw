---
title: AlphaClaw Benchmark Lab
emoji: 🦀
colorFrom: gray
colorTo: red
sdk: docker
app_port: 7860
license: mit
short_description: Compare OmegaClaw and AlphaClaw traces.
---

# AlphaClaw Benchmark Lab

This Space is intentionally non-agentic. It accepts two benchmark JSONL traces and an optional explicit rate card, then computes the same report as `benchmarks/analyze.py` in the AlphaClaw repository.

It does not retain a persona, maintain long-term memory, invoke an LLM, or make model API calls.

The benchmark accounting format is inspired by the per-call `memory/usage.jsonl` seam used by Larry Greenblatt's ThreadKeeper project.
