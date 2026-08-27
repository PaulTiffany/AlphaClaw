# External benchmark dependencies

`ThreadKeeper/` is pinned here only as an external benchmark dependency and provenance witness.

AlphaClaw runtime code in `ingress/` does not depend on ThreadKeeper. Stock OmegaClaw does not import or mount it. The benchmark controller also does not import ThreadKeeper into its own interpreter.

For accounting, the controller first preserves the provider-returned usage receipt itself. It then launches a short-lived isolated Python worker (`python -I`) that loads the exact pinned `ThreadKeeper/src/threadkeeper_budget.py` file and receives only token counts plus accounting paths.

Only ThreadKeeper's Record / Account seam is used. Its routing, escalation, memory, agent mesh, MeTTa policy, and decision logic are outside AlphaClaw's benchmark architecture.

ThreadKeeper receives no provider credentials, prompt text, response text, Docker authority, or Alpha envelope, and its measurement must not influence the Alpha sensory contract, provider selection, loop bounds, available actions, or response content.
