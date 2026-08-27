# Local Omega profile utilities

This directory is **not AlphaClaw** and not OmegaClaw.

AlphaClaw is the sensory/prepend boundary in `ingress/`. OmegaClaw itself is the pinned upstream `OmegaClaw-Core/` submodule. These utilities are a separately auditable experiment for preparing a disposable OmegaClaw working tree with reduced authority.

```text
world / human
    |
    v
AlphaClaw sensory boundary
media -> symbolic/text handoff
    |
    v
upstream OmegaClaw text inference

SEPARATE AUTHORITY PLANE:
controller/omega_profile.py
exact pinned Omega source -> deterministic reduced-authority copy
```

The separation is intentional:

```text
perception != authority != inference
```

## Upstream ownership boundary

This repository does not document or claim ownership of OmegaClaw's normal internals.

For OmegaClaw installation, operation, channels, providers, tools, architecture, and intended upstream behavior, use the documentation and source in `OmegaClaw-Core/` / `asi-alliance/OmegaClaw-Core`.

This controller only owns its own narrow claim:

> given the exact pinned upstream source shape we inspected, apply these explicit reductions or fail closed.

If upstream Omega changes such that an expected source fragment no longer matches, the correct controller behavior is refusal and human review—not silent adaptation.

## Inspect upstream state

`inspect_omega.py` reports source-state facts that help determine what interference a controller would need:

```bash
python controller/inspect_omega.py --source OmegaClaw-Core
```

Its output is **not a safety certificate and not authorization to run or deploy anything**.

## Create a local reduced-authority copy

Start with the credential-free mock profile:

```bash
python controller/omega_profile.py \
  --source OmegaClaw-Core \
  --destination /tmp/omegaclaw-profiled
```

The default profile uses `mockchannel` + `mockprovider` and applies these constraints:

```text
boot inference grant:          0
new-human-input grant:         8
scheduled-wake grant:          0
history recall:                0
persistent history writes:    disabled
model-directed actions:        send only
dynamic command expansion:    disabled
autonomous goal prompt:        removed
conversation bodies in logs:   removed
```

The controller refuses to transform an unexpected or dirty Omega source tree. It uses exact-source substitutions so upstream mechanical drift becomes a visible failure.

## Deliver one Alpha handoff to a running local mock Omega

`omega_mock_bridge.py` is a one-shot adapter around OmegaClaw's own native mock communication channel. It does not perceive input, choose models, start Omega, or change Omega authority. It accepts an already prepared Alpha text envelope, sends that exact string once, returns Omega's first reply, and exits.

After the profiled Omega process has been started separately with its `test` communication channel, Alpha output can be piped directly into the bridge:

```bash
python ingress/pipe.py --text "hello" | \
  python controller/omega_mock_bridge.py \
    --omega-source /tmp/omegaclaw-profiled
```

The same bridge receives the final Alpha envelope whether the original input took the text-passthrough path or the multimedia-perception path.

A real provider or WebSocket channel is an explicit controller invocation, for example:

```bash
python controller/omega_profile.py \
  --source OmegaClaw-Core \
  --destination /tmp/omegaclaw-profiled \
  --channel wschat \
  --provider asione
```

That choice belongs to the outer controller/operator. AlphaClaw does not select providers, channels, credentials, inference budgets, plugins, or permissions.

## Local-first testing

The intended testing order is:

```text
1. read upstream Omega documentation for upstream behavior
2. inspect the exact pinned source state we depend on
3. create a disposable profiled copy
4. mechanically test the copy locally without credentials
5. only then add one explicitly chosen real inference provider if needed
6. destroy the disposable run after the experiment
```

There is no standing resident, cloud lifecycle controller, upstream watcher, automatic promotion path, or remote kill-switch protocol in this architecture.

The default development question remains:

> **WHY DO WE NEED THAT?**

A capability is restored only after a bounded experiment demonstrates that the minimum system cannot answer the research question without it.
