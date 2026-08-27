"""One source of truth for a bounded AlphaClaw/OmegaClaw benchmark episode."""

from __future__ import annotations

from dataclasses import asdict, dataclass

DEFAULT_MAX_REASONING_LOOPS = 1
MAX_REASONING_LOOPS = 50
AFTER_RESPONSE = "wait_for_new_user_input_or_terminate"
BOOT_BEHAVIOR = "stock_omegaclaw_boot_observed_and_metered"


@dataclass(frozen=True)
class EpisodeContract:
    """Bounds announced to Omega and mechanically applied by the benchmark controller."""

    max_reasoning_loops: int = DEFAULT_MAX_REASONING_LOOPS
    max_wake_loops: int = 0
    max_history: int = 0
    after_response: str = AFTER_RESPONSE
    boot_behavior: str = BOOT_BEHAVIOR

    def __post_init__(self) -> None:
        if not 1 <= self.max_reasoning_loops <= MAX_REASONING_LOOPS:
            raise ValueError(
                f"max_reasoning_loops must be between 1 and {MAX_REASONING_LOOPS}"
            )
        if self.max_wake_loops != 0:
            raise ValueError("bounded benchmark episodes do not permit scheduled wake grants")
        if self.max_history != 0:
            raise ValueError("bounded benchmark episodes do not recall persistent history")
        if self.after_response != AFTER_RESPONSE:
            raise ValueError(f"unsupported after_response policy: {self.after_response}")
        if self.boot_behavior != BOOT_BEHAVIOR:
            raise ValueError(f"unsupported boot behavior: {self.boot_behavior}")

    def instructions(self) -> tuple[str, ...]:
        loops = self.max_reasoning_loops
        noun = "loop" if loops == 1 else "loops"
        return (
            f"This bounded benchmark episode permits at most {loops} reasoning {noun} after this human-mediated input is received.",
            f"Send your best response to the user no later than reasoning loop {loops}.",
            "After you send a response, wait for genuinely new user input; the benchmark controller will end this one-shot episode.",
            "The benchmark schedules no autonomous wake-up window before teardown.",
            "OmegaClaw's stock startup activity occurs before this handoff and is measured separately from this human-input grant.",
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
