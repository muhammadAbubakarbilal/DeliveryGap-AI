import httpx
import pytest
from app.ai_gateway import GatewayUnavailable, NeonGateway
from app.config import Settings


def test_gateway_uses_neon_env_and_bounds_output():
    def respond(request):
        assert str(request.url) == "https://gateway.example/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-only"
        assert b'"max_completion_tokens":256' in request.content
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    settings = Settings(
        neon_ai_gateway_base_url="https://gateway.example", neon_ai_gateway_token="test-only"
    )
    assert NeonGateway(settings, httpx.MockTransport(respond)).complete("Reply OK") == "OK"
    unavailable = NeonGateway(settings, httpx.MockTransport(lambda _: httpx.Response(402)))
    with pytest.raises(GatewayUnavailable, match="check plan"):
        unavailable.complete("Reply OK")


def test_gateway_fails_closed_without_credentials():
    with pytest.raises(GatewayUnavailable, match="not configured"):
        NeonGateway(Settings(neon_ai_gateway_token="")).complete("Reply OK")


def test_embedding_gateway_restores_input_order_and_validates_values():
    def respond(request):
        assert str(request.url) == "https://gateway.example/v1/embeddings"
        assert b'"dimensions":3' in request.content
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [4, 5, 6]},
                    {"index": 0, "embedding": [1, 2, 3]},
                ]
            },
        )

    gateway = NeonGateway(
        Settings(
            neon_ai_gateway_base_url="https://gateway.example",
            neon_ai_gateway_token="test-only",
        ),
        httpx.MockTransport(respond),
    )
    assert gateway.embed_many(["first", "second"], dimensions=3) == [
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
    ]


@pytest.mark.parametrize(
    "items",
    [
        [{"index": 0, "embedding": [1, 2, 3]}],
        [
            {"index": 0, "embedding": [1, 2, 3]},
            {"index": 0, "embedding": [4, 5, 6]},
        ],
        [
            {"index": 0, "embedding": [1, float("nan"), 3]},
            {"index": 1, "embedding": [4, 5, 6]},
        ],
    ],
)
def test_embedding_gateway_rejects_malformed_responses(items):
    gateway = NeonGateway(
        Settings(
            neon_ai_gateway_base_url="https://gateway.example",
            neon_ai_gateway_token="test-only",
        ),
        httpx.MockTransport(lambda _: httpx.Response(200, json={"data": items})),
    )
    with pytest.raises(GatewayUnavailable, match="embedding request failed"):
        gateway.embed_many(["first", "second"], dimensions=3)


def test_embedding_gateway_bounds_batch_size_and_input_size():
    settings = Settings(
        neon_ai_gateway_base_url="https://gateway.example",
        neon_ai_gateway_token="test-only",
    )
    gateway = NeonGateway(
        settings, httpx.MockTransport(lambda _: pytest.fail("No request expected"))
    )
    with pytest.raises(ValueError, match="between 1 and 64"):
        gateway.embed_many(["input"] * 65)
    with pytest.raises(ValueError, match="bounds"):
        gateway.embed_many(["x" * 8001])
