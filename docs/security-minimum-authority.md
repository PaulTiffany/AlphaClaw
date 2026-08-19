# Minimum-authority security decision

The first AlphaClaw resident experiment asks one question: can bounded Omega reason over a
human-mediated handoff and communicate a useful result?

That experiment does not require shell execution, web search, file mutation, arbitrary MeTTa
evaluation, long-term memory, dynamic model commands, workflow plugins, alternate providers, or
additional communication channels.

Therefore those powers are absent from the resident authority surface.

## Security rule

> A component may exercise only authority granted from outside its mutable state.

Omega may mutate internal symbolic state. Internal mutation cannot grant additional inference,
commands, plugins, credentials, persistence, or Alpha capabilities.

## Bounded recursive self-improvement

AlphaClaw permits reasoning about improvements and internal symbolic self-modification only inside
an externally fixed authority envelope. A resident may propose a change; it may not make that change
authoritative merely by proposing, evaluating, or recursively reproducing it itself.

The invariant is:

```text
recursive proposal != recursive authorization

descendant authority <= externally granted ancestor authority
```

In particular, no resident-controlled path may combine all of the following without an external
review and authorization boundary:

```text
propose -> self-evaluate -> self-deploy -> widen authority -> recurse
```

Promotion of any change that affects inference budget, callable actions, plugins, credentials,
persistence, network destinations, Alpha ingress, or the authority boundary itself must occur
outside Omega's mutable state and must preserve or reduce the resident's currently granted authority.

A model's own judgment that a modification is safe, useful, or superior is evidence to consider, not
authorization to deploy it.

## Restoration rule

A removed capability is not restored because a benchmark, demo, or convenience path expects it.
First demonstrate that the minimum experiment cannot succeed without the capability. Then add the
smallest externally bounded form and a mechanical witness for its limit.

The default question is: **WHY DO WE NEED THAT?**
