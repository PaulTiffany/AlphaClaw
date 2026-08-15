# Omega resident-model qualification

This layer answers a question between residency certification and benchmarking:

> Can this concrete model actually inhabit this concrete OmegaClaw revision?

It deliberately reuses OmegaClaw's own runtime and autotest seams instead of implementing a second agent loop.

## Provenance boundary

AlphaClaw's `certification/` derives the powers demanded by an exact OmegaClaw Git SHA. `selection/` discovers currently addressable provider models. Qualification is where a candidate model must demonstrate those powers behaviorally.

Provider metadata is not qualification. A model advertising `tools`, `reasoning`, or structured output remains unqualified until it survives OmegaClaw's actual symbolic command protocol and tool-result loop.

## Runtime strategy

The pinned OmegaClaw source already ships a deterministic autotest communication path under `Autotests/mock/`:

- its Docker image preloads the local embedding model;
- knowledge import defaults off;
- the `test` communication channel talks to a host-side `CommMockServer`;
- the ordinary OmegaClaw loop, skills, history, memory, and provider registry stay resident in the container.

AlphaClaw therefore does not add another test channel. For a qualification run:

1. build `OmegaClaw-Core/` as `omegaclaw:pinned` from the exact submodule SHA;
2. build `docker/Dockerfile.overlay` on that image;
3. start the resulting AlphaClaw image with OmegaClaw's existing `test` channel;
4. select a real provider/model, initially OpenRouter;
5. send qualification tasks through upstream's `CommMockServer`;
6. inspect both the agent's reply and the actual filesystem/history/tool effects inside the container.

The overlay image copies only `alphaclaw.metta` and `run.metta`; it preserves the upstream entrypoint and runtime implementation.

## First live residency task

The first task should be intentionally boring and multi-turn:

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
- provider and model identity are recorded with the run.

A model failing any of those remains unqualified.

## Cheapest-paid policy

Free OpenRouter routes remain visible in the census but are excluded from the default resident policy because request/day caps make a persistent OmegaClaw loop operationally fragile.

For live selection, candidates are considered in OpenRouter's published `pricing-low-to-high` order. The eventual selector should try paid candidates in that order against this qualification task and stop at the first green model.

That result may be called `cheapest_qualified_paid`.

Until the behavioral runner is executed, `selection/` may only report `cheapest_paid_candidate`.

## Benchmark boundary

Qualification asks **can this model be Omega?**

`benchmarks/` asks **given a qualified resident model, does AlphaClaw reduce expensive multimodal inference while preserving task success?**

Keeping those questions separate prevents a weak resident model from masquerading as evidence for or against the AlphaClaw architecture.
