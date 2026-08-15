from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    source_ref: str
    region: str | None = None


@dataclass(frozen=True, slots=True)
class Claim:
    proposition: str
    confidence: float
    evidence: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class Ambiguity:
    description: str
    alternatives: tuple[str, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()


@dataclass(frozen=True, slots=True)
class Observation:
    text: str
    evidence: tuple[EvidenceRef, ...] = ()


@dataclass(slots=True)
class AlphaState:
    source_ref: str
    observations: list[Observation] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    ambiguities: list[Ambiguity] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IngressRequest:
    source_ref: str
    instruction: str = "Normalize this input for symbolic reasoning."


@dataclass(frozen=True, slots=True)
class SourceQuery:
    source_ref: str
    question: str
    region: str | None = None
