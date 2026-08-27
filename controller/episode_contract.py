"""One source of truth for a bounded AlphaClaw/OmegaClaw benchmark episode."""

from __future__ import annotations

from dataclasses import asdict, dataclass

DEFAULT_MAX_REASONING_LOOPS = 50
AFTER_RESPONSE = "wait_for_new_user_input_or_terminate"


@dataclass(frozen=True)
class EpisodeContract:
    """Bounds announced to Omega and mechanically applied by the benchmark controller."""

    max_reasoning_loops: int = DEFAULT_MAX_REASONING_LOOPS
    max_wake_loops: int = 0
    max_history: int = 0
    after_response: str = AFTER_RESPONSE

    def __post_init__(self) -> None:
        if self.max_reasoning_loops <= 0:
            raise ValueError("max_reasoning_loops must be positive")
        if self.max_wake_loops != 0:
            raise ValueError("bounded benchmark episodes do not permit autonomous wake loops")
        if self.max_history != 0:
            raise ValueError("bounded benchmark episodes do not recall persistent history")
        if self.after_response != AFTER_RESPONSE:
            raise ValueError(f"unsupported after_response policy: {self.after_response}")

    def instructions(self) -> tuple[str, ...]:
        loops = self.max_reasoning_loops
        return (
            f"This bounded benchmark episode permits at most {loops} total reasoning loops for the current user input.",
            f"You must send your best response to the user no later than reasoning loop {loops}.",
            "After you send a response, your inference grant ends for this episode.",
            "After responding, wait for genuinely new user input or terminate; do not continue autonomous reasoning.",
            "There are no autonomous wake-up loops in this episode.",
        )

    def handoff(self) -> dict[str, object]:
        """Structured episode clause inserted by the controller into Alpha's fixed envelope."""
        return {
            "mode": "bounded_benchmark",
            **asdict(self),
            "instructions": list(self.instructions()),
        }

    def manifest(self) -> dict[str, object]:
        return self.handoff()
