from typing import Any

import pytest
from app.source_parsers import parse_original

from scripts import seed_supervisor_demo as demo


class FakeApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None, str | None]] = []
        self.requirement_status = "draft"

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append((method, path, body, idempotency_key))
        if path == "/api/v1/projects":
            return {"id": "project-id"}
        if path.endswith("/documents/manual"):
            return {"version_id": "source-version-id"}
        if path.endswith("/versions/source-version-id/job"):
            return {"status": "succeeded"}
        if path.endswith("/versions/source-version-id/spans"):
            return {
                "items": [
                    {
                        "id": "source-span-id",
                        "text": "REQ-003: Checkout accepts USD payments only.",
                    }
                ]
            }
        if method == "POST" and path.endswith("/requirements"):
            return {
                "id": "requirement-id",
                "versions": [
                    {
                        "id": "requirement-version-id",
                        "version_number": 1,
                        "status": "draft",
                    }
                ],
            }
        if method == "GET" and path.endswith("/requirements/requirement-id"):
            return {
                "id": "requirement-id",
                "versions": [
                    {
                        "id": "requirement-version-id",
                        "version_number": 1,
                        "status": self.requirement_status,
                    }
                ],
            }
        if method == "POST" and path.endswith("/requirements/requirement-id/approve"):
            self.requirement_status = "approved"
            return {}
        if path.endswith("/baselines"):
            return {"number": 1, "items": [{"requirement_version_id": "requirement-version-id"}]}
        return {}


def test_demo_seed_uses_the_api_to_publish_cited_single_item_baseline() -> None:
    api = FakeApi()

    demo.seed(api)

    assert api.calls[0][3] == demo.PROJECT_KEY
    source_call = next(call for call in api.calls if call[1].endswith("/documents/manual"))
    assert source_call[2] is not None
    assert "REQ-003" in source_call[2]["text"]
    requirement_call = next(call for call in api.calls if call[1].endswith("/requirements"))
    assert requirement_call[2] == {
        "code": "REQ-003",
        "title": demo.REQUIREMENT_TITLE,
        "content": demo.REQUIREMENT_TEXT,
        "source_version_id": "source-version-id",
        "source_span_id": "source-span-id",
        "source_quote": demo.REQUIREMENT_TEXT,
    }
    assert any(call[1].endswith("/requirements/requirement-id/approve") for call in api.calls)
    baseline_call = next(call for call in api.calls if call[1].endswith("/baselines"))
    assert baseline_call[2] == {"requirement_version_ids": ["requirement-version-id"]}
    assert baseline_call[3] == demo.BASELINE_KEY


def test_demo_seed_replay_does_not_reapprove_an_already_approved_requirement() -> None:
    api = FakeApi()

    demo.seed(api)
    demo.seed(api)

    approvals = [
        call for call in api.calls if call[1].endswith("/requirements/requirement-id/approve")
    ]
    assert len(approvals) == 1
    assert len([call for call in api.calls if call[1].endswith("/baselines")]) == 2


def test_demo_seed_refuses_nonlocal_api_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    assert demo.require_local_url("http://localhost:8000") == "http://localhost:8000"
    with pytest.raises(demo.DemoSeedError, match="local HTTP API URL"):
        demo.require_local_url("https://api.example.com")
    with pytest.raises(demo.DemoSeedError, match="local HTTP API URL"):
        demo.require_local_url("http://api:8000")
    monkeypatch.setenv("DELIVERYGAP_DEMO_COMPOSE", "1")
    assert demo.require_local_url("http://api:8000") == "http://api:8000"
    with pytest.raises(demo.DemoSeedError, match="local HTTP API URL"):
        demo.require_local_url("http://user:password@localhost:8000")


def test_shopflow_scope_parses_to_one_exact_usd_requirement_span() -> None:
    content = demo.SCOPE_PATH.read_bytes()
    spans, warning = parse_original("scope.md", content)
    matches = [span for span in spans if demo.REQUIREMENT_TEXT in span.text]

    assert warning is None
    assert len(matches) == 1
