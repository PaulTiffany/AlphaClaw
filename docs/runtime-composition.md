# AlphaClaw runtime composition

AlphaClaw is a boundary around a pinned OmegaClaw resident, not an agent inside it.

```text
human / media
     |
     v
external Python ingress
  - optional one multimodal translation
  - fixed Alpha directions prepended once
     |
     v
pinned stock OmegaClaw
  - provider: ASIOne
  - model: asi1-mini
  - boot inference cycles: 0
  - cycles per new human input: 8
  - scheduled wake cycles: 0
```

## Substrate

`OmegaClaw-Core` is a pristine pinned Git submodule. The Hugging Face stage copies the complete
upstream tree except Git metadata. AlphaClaw does not import an Alpha MeTTa library, replace
Omega's runner, patch the plugin loader, or install a second control loop.

## Alpha boundary

Alpha directions are prepared outside the resident by `ingress/prepend.py`. Non-text ingress may
first pass through a single external Python translation call such as `ingress/openrouter_image.py`.
The resulting handoff is fixed before it crosses into Omega.

Omega has no callback into the Alpha ingress path. If evidence is insufficient, the resident must
wait for new human-mediated input rather than autonomously re-running ingress.

## Omega dials

The resident uses Omega's native configuration surface:

```yaml
maxNewInputLoops: 8
maxWakeLoops: 0
```

The HF entrypoint binds provider/model/channel and secrets at the process boundary. It explicitly
refuses startup if an in-process `/PeTTa/repos/AlphaClaw` library exists.

## Boot gate

Pinned Omega normally initializes `&loops` to `maxNewInputLoops`, which grants inference authority
at process start. AlphaClaw makes one narrowly scoped staged compatibility transform: the deployed
copy starts `&loops` at `0` and initializes the wake timestamp. Stock Omega's existing new-human-
message refill remains unchanged and still grants `maxNewInputLoops` cycles.

The upstream submodule is never edited.

## Capability boundary

The loop budget limits inference calls. Omega's own security/tool policy independently limits what
an inference may touch. These are separate controls and should stay separate.

## Invariant

```text
Alpha = external gate
Omega = pinned reasoner
HF = embodiment
human input = inference refill authority
```

If a change requires Alpha code to live in Omega's atomspace, modifies Omega plugin semantics, adds
a second lifecycle authority, or gives Omega a callback into Alpha ingress, reject it unless a
minimal control experiment proves the requirement.
