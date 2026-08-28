"""One source of truth for a bounded AlphaClaw/OmegaClaw benchmark episode."""

from __future__ import annotations

from dataclasses import asdict, dataclass

DEFAULT_MAX_REASONING_LOOPS = 50
MAX_REASONING_LOOPS = 50
DEFAULT_MAX_BOOT_CALLS = 1
MAX_BOOT_CALLS = 50
AFTER_RESPONSE = "wait_for_new_user_input_or_terminate"
BOOT_BEHAVIOR = "stock_omegaclaw_boot_observed_and_metered"

# Fields the controller announces to Omega inside Alpha's envelope. The boot-call
# budget is deliberately absent: it bounds the controller's own willingness to
# fund upstream calls, and is not a clause Omega is told about.
OMEGA_FACING_FIELDS = (
    "max_reasoning_loops",
    "max_wake_loops",
    "max_history",
    "after_response",
    "boot_behavior",
)


@dataclass(frozen=True)
class EpisodeContract:
    """Bounds announced to Omega and mechanically applied by the benchmark controller."""

    max_reasoning_loops: int = DEFAULT_MAX_REASONING_LOOPS
    max_wake_loops: int = 0
    max_history: int = 0
    after_response: str = AFTER_RESPONSE
    boot_behavior: str = BOOT_BEHAVIOR
    max_boot_calls: int = DEFAULT_MAX_BOOT_CALLS

    def __post_init__(self) -> None:
        if not 1 <= self.max_reasoning_loops <= MAX_REASONING_LOOPS:
            raise ValueError(
                f"max_reasoning_loops must be between 1 and {MAX_REASONING_LOOPS}"
            )
        if not 1 <= self.max_boot_calls <= MAX_BOOT_CALLS:
            raise ValueError(
                f"max_boot_calls must be between 1 and {MAX_BOOT_CALLS}"
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
        """Structured episode clause inserted by the controller into Alpha's fixed envelope.

        Only Omega-facing bounds appear here. Host-side authorization budgets must
        not leak into the envelope, because that would change the observed input to
        stock Omega and contaminate the behavior the benchmark measures.
        """
        data = asdict(self)
        return {
            "mode": "bounded_benchmark",
            **{name: data[name] for name in OMEGA_FACING_FIELDS},
            "instructions": list(self.instructions()),
        }

    def bounds_config(self, *, wakeup_interval: int) -> dict[str, int]:
        """The numeric bounds Omega must receive as YAML-typed configuration.

        Omega's `src/config.py` applies no type coercion to command-line or
        environment overrides, so a numeric bound supplied that way reaches
        `src/loop.metta` as a string and fails in `is/2` arithmetic. Only the config
        file is parsed by `yaml.safe_load`, which yields real integers, so these four
        values must travel through a config file rather than argv.
        """
        if wakeup_interval < 1:
            raise ValueError("wakeup_interval must be positive")
        return {
            "maxNewInputLoops": self.max_reasoning_loops,
            "maxWakeLoops": self.max_wake_loops,
            "maxHistory": self.max_history,
            "wakeupInterval": wakeup_interval,
        }

    def bounds_yaml(self, *, wakeup_interval: int) -> str:
        """Render the bounds as a minimal YAML document.

        Deliberately minimal: Omega replaces its whole config file when one is
        selected, so every key omitted here resolves from the in-source default at
        its `(configure key default)` site. Those defaults match the pinned
        config.yaml for every key, so omitting them changes nothing.
        """
        bounds = self.bounds_config(wakeup_interval=wakeup_interval)
        return "".join(f"{key}: {value}\n" for key, value in bounds.items())

    def bounds_semantics(self) -> dict[str, str]:
        """What the bounds mechanically do -- and what they do not claim."""
        return {
            "maxNewInputLoops": (
                "bounds prompted reasoning turns per new-input activation, "
                "not raw loop ticks"
            ),
            "maxHistory": (
                "suppresses prior recalled history; the current HUMAN-MSG input is "
                "delivered outside the HISTORY field and is preserved"
            ),
            "maxWakeLoops": "suppresses wake-driven prompted work",
            "provider_calls": (
                "bounded separately and independently by the external metering gateway"
            ),
            "skill_executions": (
                "not equivalent to provider calls: one prompted turn may request up to "
                "five skills, so no one-tool ceiling is claimed"
            ),
        }

    def manifest(self) -> dict[str, object]:
        """Receipt-facing view: the handoff plus controller-only authorization bounds."""
        return {
            **self.handoff(),
            "max_boot_calls": self.max_boot_calls,
            "bounds_semantics": self.bounds_semantics(),
        }
