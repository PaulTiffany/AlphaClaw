from alphaclaw import AlphaClaw, AlphaState, EvidenceRef, IngressRequest, Observation


class FakeProvider:
    def __init__(self) -> None:
        self.normalize_calls = 0
        self.query_calls = 0

    def normalize(self, request: IngressRequest) -> AlphaState:
        self.normalize_calls += 1
        return AlphaState(
            source_ref=request.source_ref,
            observations=[
                Observation(
                    text="A diagram contains nodes A and B connected by an arrow.",
                    evidence=(EvidenceRef(request.source_ref, "full"),),
                )
            ],
            unresolved=["Arrow direction is not yet resolved."],
        )

    def query(self, request):
        self.query_calls += 1
        return Observation(
            text="The arrow points from A to B only.",
            evidence=(EvidenceRef(request.source_ref, request.region),),
        )


def test_ingress_is_one_multimodal_call() -> None:
    provider = FakeProvider()
    alpha = AlphaClaw(provider)

    state = alpha.ingest(IngressRequest(source_ref="image://demo"))

    assert state.source_ref == "image://demo"
    assert provider.normalize_calls == 1
    assert provider.query_calls == 0


def test_multimodal_requery_is_explicit_and_targeted() -> None:
    provider = FakeProvider()
    alpha = AlphaClaw(provider)
    state = alpha.ingest(IngressRequest(source_ref="image://demo"))

    answer = alpha.query_source(
        state,
        question="What direction is the arrow?",
        region="center",
    )

    assert answer.text == "The arrow points from A to B only."
    assert provider.normalize_calls == 1
    assert provider.query_calls == 1
    assert state.observations[-1] == answer


def test_provider_cannot_swap_source_identity() -> None:
    class BadProvider(FakeProvider):
        def normalize(self, request: IngressRequest) -> AlphaState:
            return AlphaState(source_ref="image://wrong")

    alpha = AlphaClaw(BadProvider())

    try:
        alpha.ingest(IngressRequest(source_ref="image://demo"))
    except ValueError as exc:
        assert "different source_ref" in str(exc)
    else:
        raise AssertionError("source mismatch must fail closed")
