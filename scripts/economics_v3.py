"""Protocol v3-B economic model: perceive-once versus perceive-every-call.

Two things are kept strictly apart:

**Architectural arithmetic.** For reasoning depth N, a multimodal-resident baseline
issues N multimodal calls and AlphaClaw issues 1. Avoided multimodal calls are ``N - 1``
and the avoidance fraction is ``1 - 1/N``. This is an implication of call structure, not
an empirical result, and is labelled as such everywhere.

**Measured cost.** Dollars come from provider receipts. Where a provider exposes only
catalog pricing, the figure is labelled an ESTIMATE and never reported as measured.

Cost equations, frozen (Amendment v3.2):

    C_MM(N)    = N * C_multimodal
    C_Alpha(N) = C_multimodal + N * C_text
    Savings(N) = N * C_multimodal - (C_multimodal + N * C_text)
               = (N - 1) * C_multimodal - N * C_text
    fraction   = 1 - C_Alpha(N) / C_MM(N)                (defined for N > 0)
    limit      = 1 - C_text / C_multimodal               (stationary prices, N -> inf)

Reasoning depth is held CONSTANT across architectures: at depth N every arm performs N
reasoning calls. E2 additionally makes exactly one perception call, an architectural
setup cost that is NOT one of the N reasoning steps, so E2 issues N + 1 provider calls
per episode. The superseded ``C_multimodal + (N - 1) * C_text`` assumed total-call
parity instead, which would have given E2 one fewer reasoning step than E1 and E3.

A consequence to preserve rather than hide: at N = 1 AlphaClaw pays one perception plus
one text call against the baseline's single multimodal call, so negative dollar savings
at shallow depth is a legitimate result. The economic claim is amortisation, not a
guarantee of a break-even depth inside {1, 2, 4, 8}; break-even is derived only from
receipts.

A cheaper architecture that fails the frozen success criterion is NOT economically
superior. The primary economic figure is therefore **cost per successful episode**.
"""

from __future__ import annotations

from typing import Any

E1_MULTIMODAL_RESIDENT = "E1_multimodal_resident"
E2_ALPHACLAW = "E2_alphaclaw"
E3_TEXT_ORACLE = "E3_text_oracle"

ARCHITECTURES = (E1_MULTIMODAL_RESIDENT, E2_ALPHACLAW, E3_TEXT_ORACLE)

#: Preregistered reasoning depths for the first tranche. Deliberately small.
DEPTHS = (1, 2, 4, 8)

MEASURED = "measured"
ESTIMATED = "estimated"

AMENDMENT_VERSION = "v3.2"

#: Superseded by Amendment v3.2. Retained only so a test can prove it is not used.
SUPERSEDED_ALPHA_COST_FORMULA = "C_multimodal + (N - 1) * C_text"


class EconomicsError(ValueError):
    """A comparison was requested that the preregistration forbids."""


# --- architectural arithmetic (not an empirical result) -----------------------


def reasoning_steps(architecture: str, depth: int) -> int:
    """Reasoning-step parity: every architecture performs exactly ``depth`` steps."""
    if architecture not in ARCHITECTURES:
        raise EconomicsError(f"unknown architecture {architecture!r}")
    return depth


def perception_calls(architecture: str, depth: int) -> int:
    """Architectural setup cost. Only E2 pays it, and only once."""
    if architecture not in ARCHITECTURES:
        raise EconomicsError(f"unknown architecture {architecture!r}")
    if architecture == E1_MULTIMODAL_RESIDENT:
        return 0        # E1's multimodal calls ARE its reasoning calls
    return 1 if architecture == E2_ALPHACLAW else 0


def expected_call_structure(depth: int) -> dict[str, Any]:
    """Call counts implied by each architecture at reasoning depth ``depth``.

    Depth is reasoning steps, held constant across arms. E2's single perception call is
    additional, so E2 issues ``depth + 1`` provider calls per episode.
    """
    if depth < 1:
        raise EconomicsError("reasoning depth must be at least 1")
    return {
        "depth": depth,
        E1_MULTIMODAL_RESIDENT: {"multimodal_calls": depth, "text_calls": 0},
        E2_ALPHACLAW: {"multimodal_calls": 1, "text_calls": depth},
        E3_TEXT_ORACLE: {"multimodal_calls": 0, "text_calls": depth},
        "reasoning_steps_per_arm": depth,
        "e2_perception_calls": 1,
        "e2_total_provider_calls": depth + 1,
        "multimodal_calls_avoided": depth - 1,
        "multimodal_avoidance_fraction": 1 - (1 / depth),
        "metric_scope": ("multimodal inference avoidance; NOT total provider-call "
                         "avoidance"),
        "label": "architectural arithmetic; not an empirical result",
    }


def expected_call_table() -> list[dict[str, Any]]:
    return [expected_call_structure(n) for n in DEPTHS]


def receipts_match_expected(
    *, depth: int, architecture: str, multimodal_calls: int, text_calls: int
) -> dict[str, Any]:
    """Check observed receipts against the architecture's implied call structure."""
    if architecture not in ARCHITECTURES:
        raise EconomicsError(f"unknown architecture {architecture!r}")
    expected = expected_call_structure(depth)[architecture]
    return {
        "architecture": architecture,
        "depth": depth,
        "expected_multimodal_calls": expected["multimodal_calls"],
        "observed_multimodal_calls": multimodal_calls,
        "expected_text_calls": expected["text_calls"],
        "observed_text_calls": text_calls,
        "matches": (multimodal_calls == expected["multimodal_calls"]
                    and text_calls == expected["text_calls"]),
    }


# --- frozen cost equations ----------------------------------------------------


def cost_multimodal_resident(depth: int, c_multimodal: float) -> float:
    """C_MM(N) = N * C_multimodal"""
    return depth * c_multimodal


def cost_alphaclaw(depth: int, c_multimodal: float, c_text: float) -> float:
    """C_Alpha(N) = C_multimodal + N * C_text  (Amendment v3.2)

    One perception call plus N text reasoning calls: reasoning-step parity with E1.
    """
    return c_multimodal + depth * c_text


def savings(depth: int, c_multimodal: float, c_text: float) -> float:
    """Savings(N) = (N - 1) * C_multimodal - N * C_text  (Amendment v3.2)

    May be negative at shallow depth. That is a real result, not an error.
    """
    return (cost_multimodal_resident(depth, c_multimodal)
            - cost_alphaclaw(depth, c_multimodal, c_text))


def savings_fraction(depth: int, c_multimodal: float, c_text: float) -> float:
    """1 - C_Alpha(N) / C_MM(N)"""
    baseline = cost_multimodal_resident(depth, c_multimodal)
    if baseline == 0:
        raise EconomicsError("multimodal-resident baseline cost is zero")
    return 1 - cost_alphaclaw(depth, c_multimodal, c_text) / baseline


def stationary_limit(c_multimodal: float, c_text: float) -> float:
    """1 - C_text / C_multimodal, as N -> infinity with stationary prices."""
    if c_multimodal == 0:
        raise EconomicsError("multimodal unit cost is zero")
    return 1 - c_text / c_multimodal


# --- success-adjusted economics ----------------------------------------------


def cost_per_successful_episode(
    *, total_cost: float, successful_episodes: int, provenance: str
) -> dict[str, Any]:
    """The primary economic figure. Undefined -- not zero, not infinity -- at 0 successes."""
    if provenance not in (MEASURED, ESTIMATED):
        raise EconomicsError(f"cost provenance must be {MEASURED!r} or {ESTIMATED!r}")
    return {
        "total_cost": total_cost,
        "successful_episodes": successful_episodes,
        "cost_per_successful_episode": (total_cost / successful_episodes
                                        if successful_episodes else None),
        "defined": successful_episodes > 0,
        "cost_provenance": provenance,
        "note": ("A cheaper architecture that fails the frozen success criterion is not "
                 "economically superior. With zero successful episodes, cost per "
                 "success is undefined and must not be reported as favourable."),
    }


def economically_superior(a: dict[str, Any], b: dict[str, Any]) -> str | None:
    """Compare two architectures on cost per SUCCESSFUL episode.

    Returns the winning label, or ``None`` when the comparison is not supportable --
    which includes the case where one side never succeeded.
    """
    if not (a.get("defined") and b.get("defined")):
        return None
    if a["cost_per_successful_episode"] == b["cost_per_successful_episode"]:
        return None
    return a["label"] if (a["cost_per_successful_episode"]
                          < b["cost_per_successful_episode"]) else b["label"]


def summarise(
    *, architecture: str, depth: int, multimodal_calls: int, text_calls: int,
    input_tokens: int, output_tokens: int, total_cost: float,
    successful_episodes: int, attempted_episodes: int, cost_provenance: str,
) -> dict[str, Any]:
    """One architecture at one depth, with measured/estimated labelling preserved."""
    structure = receipts_match_expected(
        depth=depth, architecture=architecture,
        multimodal_calls=multimodal_calls, text_calls=text_calls)
    success = cost_per_successful_episode(
        total_cost=total_cost, successful_episodes=successful_episodes,
        provenance=cost_provenance)
    return {
        "architecture": architecture,
        "depth": depth,
        "call_structure": structure,
        "multimodal_calls": multimodal_calls,
        "text_calls": text_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "attempted_episodes": attempted_episodes,
        "successful_episodes": successful_episodes,
        "exact_match_rate": (successful_episodes / attempted_episodes
                             if attempted_episodes else None),
        **success,
    }
