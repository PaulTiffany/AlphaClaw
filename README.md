# AlphaClaw

**Multimodal at the boundary. Symbolic in the loop.**

AlphaClaw is a thin multimodal ingress layer for text-first agent systems such as OmegaClaw.
Instead of paying for multimodal inference throughout an agent trajectory, AlphaClaw performs
one multimodal normalization pass at ingress, compiles the result into a compact symbolic/text
working state, and lets the downstream agent reason over that state cheaply. The original
source remains addressable so the agent can selectively call multimodal models again only when
uncertainty requires it.

```text
user input
   |
   v
multimodal boundary model   <- one normalization call
   |
   v
AlphaClaw IR
   |
   v
text/symbolic reasoning loop
   |
   +----> targeted multimodal query when needed
```

## Design thesis

Multimodality should be a capability that can be invoked at the boundary of need, not necessarily
a property resident in every inference step.

AlphaClaw therefore separates:

1. **Observation** — what the source literally contains.
2. **Interpretation** — structured entities and relations inferred from it.
3. **Claims** — propositions suitable for downstream reasoning.
4. **Uncertainty** — ambiguities and unresolved regions that should not be silently collapsed.
5. **Provenance** — a durable handle back to the original evidence.

## Initial API

```python
from alphaclaw import AlphaClaw, IngressRequest

state = AlphaClaw(multimodal_provider).ingest(
    IngressRequest(source_ref="image://demo", instruction="Normalize for symbolic reasoning")
)

print(state.claims)
```

When a downstream text agent needs more perceptual detail:

```python
answer = alphaclaw.query_source(
    state,
    question="Is the arrow between node A and node B bidirectional?",
    region="upper-right",
)
```

That answer is returned as another provenance-bearing observation rather than being allowed to
silently rewrite prior state.

## Hypersprint target

The first benchmark is intentionally narrow:

> For the same multimodal task success, how many multimodal calls/tokens are actually necessary?

A baseline can keep a multimodal model resident throughout the reasoning trajectory. AlphaClaw
uses one ingress call plus `k` targeted re-queries, then compares task success, multimodal token
usage, total cost, and latency.

## Status

Early hypersprint prototype. The repository currently defines the symbolic handoff contract and
provider interface; concrete provider adapters and OmegaClaw integration are next.

## License

MIT © 2026 Paul Carver Tiffany III.
