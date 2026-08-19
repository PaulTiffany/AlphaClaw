# Omega resident-model qualification

This layer answers a question between residency certification and benchmarking:

> Can this concrete model actually inhabit this concrete OmegaClaw revision?

It deliberately reuses OmegaClaw's own runtime and autotest seams instead of implementing a second agent loop.

## Provenance boundary

AlphaClaw's `certification/` derives the powers demanded by an exact OmegaClaw Git SHA. Qualification is where a concrete provider/model must demonstrate those powers behaviorally.

Provider metadata is not qualification. A model advertising tools, reasoning, or structured output remains unqualified until it survives OmegaClaw's actual symbolic command protocol and tool-result loop.

## Current provider lanes

AlphaClaw currently keeps two inference roles distinct:

- **Default resident:** `ASIOne / asi1-mini`. This is the always-available symbolic resident used by the AlphaClaw runtime.
- **Sponsored test lane:** `ASICloud / minimax/minimax-m3`. This exercises the HyperSprint-sponsored MiniMax key without changing the resident default.

The same bounded residency harness is used for both lanes. Provider and model are explicit inputs to `qualification/run_omega_residency.py`; the resulting evidence records provider, model, source SHA, call count, and observed effects.

The sponsor credential is supplied only as the GitHub Actions secret `ASI_API_KEY`, which is also the environment variable expected by pinned OmegaClaw's ASI Cloud provider. The key is never committed, serialized into evidence, or intentionally printed. Qualification logs are redacted before artifact upload.

The ASI:One lane keeps the repository-facing secret `ASI_ONE_API_KEY` and bridges it to pinned OmegaClaw's expected `ASIONE_API_KEY` only in the qualification process environment.

## Runtime strategy

The pinned OmegaClaw source already ships a deterministic autotest communication path under `Autotests/mock/`:

- its Docker image preloads the local embedding model;
- knowledge import defaults off;
- the `test` communication channel talks to a host-side `CommMockServer`;
- the ordinary OmegaClaw loop, skills, history, memory, and provider registry stay resident in the container.

AlphaClaw therefore does not add another test channel. For a qualification run:

1. stage the exact pinned OmegaClaw source with the AlphaClaw overlay;
2. bake the read-only AlphaClaw finite-life config into the image;
3. start the image through OmegaClaw's existing `test` channel;
4. select the concrete provider/model under test;
5. send a deterministic symbolic task through upstream's `CommMockServer`;
6. inspect both the reply and the actual filesystem/history/tool effects inside the container;
7. fail if the external qualification call ceiling is exceeded.

The residency image preserves OmegaClaw's stock entrypoint. The AlphaClaw image-level config still applies, so the resident sees the same finite-life embodiment as the normal deployment: eight cycles after new human input and zero scheduled wake cycles.

## First live residency task

The current task is intentionally boring and multi-turn:

1. receive a unique marker and a requested JSON object;
2. call `get-io-policy` and wait for its returned result before writing;
3. create the JSON file using OmegaClaw's normal file skills;
4. on a later iteration, read the file back;
5. verify the parsed values and requested invariant from the returned evidence;
6. only then `send` the success marker.

Mechanical success requires all of the following:

- the final success marker arrives through the upstream test communication channel;
- the file exists inside the actual Omega container;
- Python can parse it as JSON;
- its values exactly match the requested mutation;
- the Omega history/log demonstrates later-turn tool-result continuation rather than a one-shot unsupported claim;
- the Alpha inference contract appears in the model context;
- provider and model identity are recorded with the run;
- the model stays within the bounded call ceiling.

A model failing any of those remains unqualified.

## Benchmark boundary

Qualification asks **can this model be Omega?**

`benchmarks/` asks **given a qualified resident model, does AlphaClaw preserve task success while moving expensive perception out of the resident loop?**

Keeping those questions separate prevents a weak resident model from masquerading as evidence for or against the AlphaClaw architecture.
