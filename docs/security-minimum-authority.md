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

## Restoration rule

A removed capability is not restored because a benchmark, demo, or convenience path expects it.
First demonstrate that the minimum experiment cannot succeed without the capability. Then add the
smallest externally bounded form and a mechanical witness for its limit.

The default question is: **WHY DO WE NEED THAT?**
