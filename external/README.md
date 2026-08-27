# External benchmark dependencies

`ThreadKeeper/` is pinned here only as an external benchmark dependency.

AlphaClaw runtime code in `ingress/` does not depend on ThreadKeeper. The benchmark controller may mount ThreadKeeper read-only and instrument the provider boundary of a disposable Omega benchmark copy so real token usage can be recorded.

Only ThreadKeeper's accounting seam is used. Its routing, escalation, memory, agent mesh, and decision policy are not part of AlphaClaw's benchmark architecture.

ThreadKeeper measurement must not influence the Alpha sensory contract, provider selection, loop bounds, available actions, or response content.