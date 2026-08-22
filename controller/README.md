# Omega controller utilities

This directory is **not AlphaClaw**.

AlphaClaw is the sensory/prepend boundary in `ingress/`. These utilities are a separately auditable control-plane experiment for preparing an OmegaClaw working tree with reduced authority.

```text
world / human
    |
    v
AlphaClaw sensory boundary
media -> symbolic/text handoff
    |
    v
OmegaClaw text inference

SEPARATE AUTHORITY PLANE:
controller/omega_profile.py
exact Omega source -> deterministic reduced-authority copy
```

The separation is intentional:

```text
perception != authority != inference
```

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

The controller refuses to transform an unexpected or dirty Omega source tree. It also uses exact-source substitutions so upstream mechanical drift becomes a failure requiring human review rather than a silent adaptation.

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
1. inspect exact upstream source
2. create disposable profiled copy
3. mechanically test the copy locally without credentials
4. only then add one explicitly chosen real inference provider if needed
5. destroy the disposable run after the experiment
```

There is no standing resident, cloud lifecycle controller, upstream watcher, automatic promotion path, or remote kill-switch protocol in this architecture.

The default development question remains:

> **WHY DO WE NEED THAT?**

A capability is restored only after a bounded experiment demonstrates that the minimum system cannot answer the research question without it.
