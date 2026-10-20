"""Bounded Neon AI Gateway adapter for worker and operator use."""

import math

import httpx

from app.config import Settings, get_settings


class GatewayUnavailable(Exception):
    pass


class NeonGateway:
    def __init__(
        self, settings: Settings | None = None, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport

    def complete(self, prompt: str, model: str = "gpt-5-mini", max_tokens: int = 256) -> str:
        if not 1 <= max_tokens <= 4000:
            raise ValueError("Output budget must be between 1 and 4000 tokens")
        if not self.settings.neon_ai_gateway_token or not self.settings.neon_ai_gateway_base_url:
            raise GatewayUnavailable("Neon AI Gateway credentials are not configured")
        if not prompt.strip() or len(prompt) > 20_000:
            raise ValueError("Prompt must contain 1–20000 characters")
        try:
            with httpx.Client(
                timeout=45, transport=self.transport, follow_redirects=False
            ) as client:
                response = client.post(
                    self.settings.neon_ai_gateway_base_url.rstrip("/") + "/v1/chat/completions",
                    headers={"Authorization": "Bearer " + self.settings.neon_ai_gateway_token},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_completion_tokens": max_tokens,
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise GatewayUnavailable("AI Gateway returned no text")
                return content
        except httpx.HTTPStatusError as exc:
            raise GatewayUnavailable(
                f"AI Gateway returned HTTP {exc.response.status_code}; "
                "check plan, credits and configuration"
            ) from exc
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            # Never include provider response bodies or request credentials in failures.
            raise GatewayUnavailable(
                "AI Gateway request failed; check plan, credits and configuration"
            ) from exc

    def embed_many(
        self,
        inputs: list[str],
        model: str = "qwen3-embedding-0-6b",
        dimensions: int = 1024,
    ) -> list[list[float]]:
        if not inputs or len(inputs) > 64:
            raise ValueError("Embedding requests must contain between 1 and 64 inputs")
        if not 1 <= dimensions <= 4096 or any(
            not value.strip() or len(value) > 8000 for value in inputs
        ):
            raise ValueError("Embedding inputs exceed the configured bounds")
        if not self.settings.neon_ai_gateway_token or not self.settings.neon_ai_gateway_base_url:
            raise GatewayUnavailable("Neon AI Gateway credentials are not configured")
        try:
            with httpx.Client(
                timeout=45, transport=self.transport, follow_redirects=False
            ) as client:
                response = client.post(
                    self.settings.neon_ai_gateway_base_url.rstrip("/") + "/v1/embeddings",
                    headers={"Authorization": "Bearer " + self.settings.neon_ai_gateway_token},
                    json={
                        "model": model,
                        "input": inputs,
                        "dimensions": dimensions,
                        "encoding_format": "float",
                    },
                )
                response.raise_for_status()
                items = response.json()["data"]
                if not isinstance(items, list) or len(items) != len(inputs):
                    raise ValueError("Embedding response count mismatch")
                embeddings: list[list[float] | None] = [None] * len(inputs)
                for item in items:
                    index = item["index"]
                    raw = item["embedding"]
                    if (
                        not isinstance(index, int)
                        or isinstance(index, bool)
                        or not 0 <= index < len(inputs)
                        or embeddings[index] is not None
                        or not isinstance(raw, list)
                        or len(raw) != dimensions
                        or any(
                            isinstance(value, bool)
                            or not isinstance(value, (int, float))
                            or not math.isfinite(value)
                            for value in raw
                        )
                    ):
                        raise ValueError("Embedding response is invalid")
                    embeddings[index] = [float(value) for value in raw]
                if any(embedding is None for embedding in embeddings):
                    raise ValueError("Embedding response is incomplete")
                return [embedding for embedding in embeddings if embedding is not None]
        except httpx.HTTPStatusError as exc:
            raise GatewayUnavailable(
                f"AI Gateway returned HTTP {exc.response.status_code}; "
                "check plan, credits and configuration"
            ) from exc
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            raise GatewayUnavailable(
                "AI Gateway embedding request failed; check model, plan and configuration"
            ) from exc
