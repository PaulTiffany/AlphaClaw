# AlphaClaw

**Multimodal at the boundary. Text inference in the loop. Authority somewhere else.**

AlphaClaw is a small sensory tool for a text-only reasoning process.

It does not own the reasoning loop, lifecycle, memory, permissions, deployment, model selection, or recursive authorization. Its job is narrower:

```text
human / world
    |
    v
AlphaClaw sensory boundary
optional one multimodal inference
observation + interpretation + uncertainty + provenance
    |
    v
fixed inert text/data prepend
    |
    v
OmegaClaw text inference
```

For already-textual input, AlphaClaw preserves the evidence and wraps it in a fixed data-only boundary envelope. For non-text evidence, one external sensory inference first translates the evidence into a symbolic/text handoff. Omega then receives text.

## The boundary

`ingress/prepend.py` is the core interface:

```bash
python ingress/prepend.py --text "your message"
```

It returns JSON data. Payloads that look like MeTTa, shell, code, prompts, or commands remain strings. AlphaClaw does not import or evaluate them.

For an image, a sensory adapter may run once before the prepend:

```bash
python ingress/openrouter_image.py \
  --image image.png \
  --output handoff.json

python ingress/prepend.py --input-file handoff.json
```

The sensory handoff separates:

```text
observation
interpretation
uncertainty
unresolved evidence
entities / relations
provenance
```

The multimodal model is therefore a perceptual translator, not an agent and not an authority source.

## What AlphaClaw does not do

AlphaClaw does not:

- run a resident agent;
- decide how many inference cycles Omega receives;
- choose or widen Omega tools;
- persist Omega memory;
- wake Omega autonomously;
- manage cloud deployments;
- inspect upstream releases on a schedule;
- select providers for Omega;
- certify Omega as safe;
- let model judgment authorize deployment or authority growth.

Those concerns must remain outside the sensory boundary.

## Separate Omega controller experiment

`controller/` contains a separately auditable deterministic utility for inspecting one exact OmegaClaw tree and producing a reduced-authority local working copy.

It is deliberately **not AlphaClaw**.

```text
perception != authority != inference
```

The controller defaults to a credential-free mock profile and fails closed if the pinned upstream mechanics drift. See `controller/README.md`.

The repository keeps `OmegaClaw-Core/` as a pristine Git submodule so the sensory interface and any controller experiment can be tested against an exact upstream source without silently folding Alpha code into Omega.

## Local-first testing

Testing should be disposable and local wherever possible:

```text
exact pinned source
      |
      v
optional deterministic controller profile
      |
      v
local bounded experiment
      |
      v
process/container destroyed
```

CI should test deterministic source properties and transformations without provider secrets. Live-provider experiments belong at the human-operated edge, not in standing repository automation.

## Development invariant

Before adding a mechanism, capability, workflow, resident process, or controller layer, ask:

> **WHY DO WE NEED THAT?**

If the research question can be answered without it, leave it absent.

**Alpha senses. Omega reasons. Authority stays outside both.**

## Philosophy

`PHILOSOPHY.md` is the normative human-facing companion to the mechanical boundary. It includes the repository's broader commitments around fallibility, recoverability, provenance, operator slack, capability versus permission, and bounded recursive improvement.

## License

AlphaClaw original code: MIT © 2026 Paul Carver Tiffany III.

`OmegaClaw-Core` remains an upstream dependency and retains its own upstream license and notices.
