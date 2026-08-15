# AlphaClaw

**Multimodal at the boundary. Symbolic in the loop.**

AlphaClaw is an opinionated composition of **OmegaClaw**, not a reimplementation of it.
The upstream `asi-alliance/OmegaClaw-Core` repository is carried intact as a pinned Git
submodule. AlphaClaw owns only the boundary machinery required to turn multimodal input into a
symbolic/text working state, hand that state to OmegaClaw, and expose multimodal models back to
OmegaClaw as explicit tools when perception is needed again.

```text
multimodal user input
        |
        v
  Alpha boundary          one multimodal normalization call
        |
        v
 symbolic/text state
        |
        v
+------------------+
|   OmegaClaw-Core |      upstream submodule; symbolic agent loop
+------------------+
        |
        +-----------> Alpha multimodal tool
                         only when OmegaClaw asks
```

## The architectural constraint

**OmegaClaw stays upstream.** AlphaClaw does not fork or casually edit its cognitive core.
Integration should happen beside it through the narrowest available extension surface.

That gives us two independently inspectable layers:

- **OmegaClaw-Core** — the symbolic/stateful reasoning engine, pinned to an upstream commit.
- **AlphaClaw** — multimodal ingress, symbolic handoff, selective multimodal tooling, adapters,
  instrumentation, and benchmarks.

If an integration requires upstream changes, the preferred order is:

1. use an existing OmegaClaw extension point;
2. add an AlphaClaw-side adapter or launcher;
3. propose a general-purpose upstream change;
4. only as a last resort carry a clearly isolated patch.

The submodule itself should remain clean.

## Thesis

Do not keep expensive multimodal intelligence resident in every reasoning step.

1. Observe multimodal input once.
2. Compile it into a provenance-bearing symbolic/text representation.
3. Let OmegaClaw reason over that representation.
4. Re-open the original evidence through a multimodal tool only when OmegaClaw identifies a
   perceptual gap.

The scaling object is the **shared symbolic state**, not the pixels.

## Repository layout

```text
AlphaClaw/
├── OmegaClaw-Core/       # pinned upstream git submodule
├── src/alphaclaw/        # Alpha boundary/tooling code
├── tests/                # Alpha contract tests
├── .gitmodules
├── pyproject.toml
└── README.md
```

The current Python package is intentionally small. It is boundary code, not a competing agent
framework.

## Clone

```bash
git clone --recurse-submodules https://github.com/PaulTiffany/AlphaClaw.git
cd AlphaClaw
```

For an existing clone:

```bash
git submodule update --init --recursive
```

## Boundary contract

AlphaClaw preserves three distinctions that must not be collapsed by the ingress model:

1. **Observation** — what the source literally contains.
2. **Interpretation** — structured entities and relations inferred from it.
3. **Claims** — propositions offered to OmegaClaw for reasoning.

It also preserves uncertainty and a durable source handle so OmegaClaw can ask a targeted
multimodal question instead of hallucinating through missing perception.

## Hypersprint benchmark

The first benchmark asks a deliberately simple question:

> For equivalent task success, how much multimodal inference is actually necessary?

Compare a multimodal-resident baseline against AlphaClaw's:

```text
1 ingress call + k targeted multimodal tool calls + symbolic OmegaClaw trajectory
```

Measure task success, multimodal calls/tokens, total inference cost, and latency.

## Upstream

OmegaClaw-Core is an upstream dependency and retains its own Apache-2.0 license and notices.
AlphaClaw's original code is licensed separately under MIT.

## License

MIT © 2026 Paul Carver Tiffany III.
