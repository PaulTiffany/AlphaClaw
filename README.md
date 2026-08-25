# AlphaClaw

**Multimodal at the boundary. Text inference in the loop. Human authority around both.**

AlphaClaw is a small sensory tool for a text-only reasoning process.

The repository also contains two deliberately separate supporting surfaces: a public human-development Wiki and a local authority-reduction experiment for one exact pinned OmegaClaw source tree. They should not be confused with AlphaClaw itself.

```text
1. PERCEPTION
human / world
    -> AlphaClaw sensory boundary
    -> inert text/data handoff

2. INFERENCE
text handoff
    -> upstream OmegaClaw

3. HUMAN DEVELOPMENT
GitHub Wiki
    -> public authored pages
```

The first is AlphaClaw proper. The second is an upstream dependency. The third is a small Git-backed place where a person can contribute documentation directly.

## 1. AlphaClaw: sensory boundary

`ingress/` contains the AlphaClaw runtime idea.

For already-textual input, `ingress/prepend.py` preserves the evidence and wraps it in a fixed data-only boundary envelope:

```bash
python ingress/prepend.py --text "your message"
```

For non-text evidence, one external sensory inference may translate the evidence before that prepend:

```bash
python ingress/openrouter_image.py \
  --image image.png \
  --output handoff.json

python ingress/prepend.py --input-file handoff.json
```

The sensory handoff separates observation, interpretation, uncertainty, unresolved evidence, entities/relations, and provenance.

The multimodal model is a perceptual translator, not an agent and not an authority source.

AlphaClaw does not own the reasoning loop, lifecycle, memory, permissions, deployment, model selection, or recursive authorization.

## 2. OmegaClaw: pinned upstream dependency

This repository does **not** implement OmegaClaw.

`OmegaClaw-Core/` is a pristine Git submodule pinned to one exact revision of the upstream `asi-alliance/OmegaClaw-Core` project. AlphaClaw does not silently fork it, rebrand its internals, or treat its implementation as AlphaClaw code.

For OmegaClaw installation, operation, internal architecture, channels, providers, tools, and normal behavior, refer to the upstream OmegaClaw documentation and source. Questions or defects intrinsic to OmegaClaw belong upstream.

What this repository owns is narrower:

- the exact upstream revision it chooses to test against;
- the sensory interface presented to a text-reasoning process;
- a separate deterministic experiment for reducing authority in a disposable local Omega working copy.

That last experiment lives in `controller/`. It is deliberately **not AlphaClaw**. It is also not an upstream OmegaClaw implementation; it is our local transformation utility. See `controller/README.md`.

```text
perception != authority != inference
```

## 3. Contributor Wiki

The [AlphaClaw Wiki](https://github.com/PaulTiffany/AlphaClaw/wiki) is the whole beginner contributor surface.

A Wiki save changes the Wiki only. It does not run OmegaClaw, become AlphaClaw sensory input, change `main`, or trigger an automatic path into the codebase.

The beginner goal is simply to make two public Wiki pages. No command-line Git is required.

`contributor/README.md` is the short source text mirrored to the Wiki Home page.

## Local-first controller experiments

`controller/` contains separately auditable utilities for inspecting the exact pinned Omega source and producing a reduced-authority local copy. The default profile is credential-free and fail-closed against unexpected source drift.

Testing should remain disposable and local wherever possible:

```text
exact pinned upstream source
      |
      v
optional deterministic profile
      |
      v
local bounded experiment
      |
      v
process/container destroyed
```

Live-provider experiments belong at the human-operated edge, not in standing repository automation.

## Development invariant

Before adding a mechanism, capability, workflow, resident process, or controller layer, ask:

> **WHY DO WE NEED THAT?**

Documentation machinery has to answer the same question. A runtime capability must also justify the authority it adds.

**Alpha senses. Omega reasons. Humans develop and authorize.**

## Philosophy

`PHILOSOPHY.md` is the normative human-facing companion to these boundaries. It includes commitments around fallibility, recoverability, provenance, operator slack, capability versus permission, and bounded recursive improvement.

## License and attribution

AlphaClaw original code: MIT © 2026 Paul Carver Tiffany III.

`OmegaClaw-Core` is upstream work and retains its own upstream license, authorship, documentation, and notices.
