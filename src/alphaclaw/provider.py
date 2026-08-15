from __future__ import annotations

from typing import Protocol

from .model import AlphaState, IngressRequest, Observation, SourceQuery


class MultimodalProvider(Protocol):
    """Boundary capability used only for ingress and targeted perceptual queries."""

    def normalize(self, request: IngressRequest) -> AlphaState:
        """Compile multimodal input into AlphaClaw's symbolic working state."""
        ...

    def query(self, request: SourceQuery) -> Observation:
        """Answer one targeted question against the retained source evidence."""
        ...
