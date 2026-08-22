#!/usr/bin/env python3
"""Exhaustive mechanical witness for bounded reciprocal disclosure.

This is deliberately not an LLM test.  It is a finite exemplar of the
architectural claim that usefulness pressure need not imply boundary crossing.

The resident has exactly three outward action kinds:

    ANSWER(value)
    DECLINE
    ASK_PERMISSION(field)

A separate verifier checks every reachable query/permission combination.
The script exits non-zero if any reachable case violates the contract.
"""

from __future__ import annotations

from itertools import product

PRIVATE = {"name": "A", "color": "blue", "secret": 42}
BLANKET = frozenset({"name", "color"})
QUERIES = ("name", "color", "secret", "nonexistent")
PERMISSION_SETS = (frozenset(), frozenset({"secret"}))


def contract(field: str, permissions: frozenset[str]) -> bool:
    """Return whether this field may cross the boundary."""
    return field in BLANKET or field in permissions


def script(field: str, permissions: frozenset[str]) -> tuple[str, object | None]:
    """Deterministic resident action within a finite action alphabet."""
    if field not in PRIVATE:
        return ("DECLINE", None)
    if contract(field, permissions):
        return ("ANSWER", PRIVATE[field])
    return ("ASK_PERMISSION", field)


def verify(
    field: str,
    action: tuple[str, object | None],
    permissions: frozenset[str],
) -> bool:
    """Independent checker; the acting script does not certify itself."""
    kind, payload = action

    if kind == "ANSWER":
        return contract(field, permissions) and payload == PRIVATE[field]
    if kind == "ASK_PERMISSION":
        return field in PRIVATE and not contract(field, permissions) and payload == field
    if kind == "DECLINE":
        return field not in PRIVATE and payload is None
    return False


def main() -> None:
    checked = 0

    for field, permissions in product(QUERIES, PERMISSION_SETS):
        action = script(field, permissions)
        if not verify(field, action, permissions):
            raise SystemExit(
                "WITNESS FAIL: "
                f"query={field!r} permissions={sorted(permissions)!r} action={action!r}"
            )
        checked += 1

    without_permission = script("secret", frozenset())
    with_permission = script("secret", frozenset({"secret"}))

    assert without_permission == ("ASK_PERMISSION", "secret")
    assert with_permission == ("ANSWER", 42)

    print(f"WITNESS PASS: {checked} reachable cases exhaustively verified")
    print("secret without permission -> ASK_PERMISSION")
    print("secret with permission    -> ANSWER")


if __name__ == "__main__":
    main()
