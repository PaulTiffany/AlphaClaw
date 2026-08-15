from __future__ import annotations

from .model import AlphaState, IngressRequest, Observation, SourceQuery
from .provider import MultimodalProvider


class AlphaClaw:
    """Thin boundary wrapper around a multimodal provider.

    The downstream reasoning system receives only AlphaState. The original source
    remains addressable through source_ref for explicit, targeted re-query.
    """

    def __init__(self, provider: MultimodalProvider) -> None:
        self._provider = provider

    def ingest(self, request: IngressRequest) -> AlphaState:
        state = self._provider.normalize(request)
        if state.source_ref != request.source_ref:
            raise ValueError("provider returned state for a different source_ref")
        return state

    def query_source(
        self,
        state: AlphaState,
        *,
        question: str,
        region: str | None = None,
    ) -> Observation:
        observation = self._provider.query(
            SourceQuery(source_ref=state.source_ref, question=question, region=region)
        )
        state.observations.append(observation)
        return observation
