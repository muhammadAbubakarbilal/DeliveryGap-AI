"""Create the minimal ShopFlow project and one-item baseline through the local API."""

from __future__ import annotations

import getpass
import os
import time
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[1]
SCOPE_PATH = ROOT / "datasets" / "synthetic_project" / "scope.md"
PROJECT_NAME = "ShopFlow — E-commerce Platform Development"
PROJECT_DESCRIPTION = "Synthetic supervisor demonstration project."
REQUIREMENT_TITLE = "USD-only checkout"
REQUIREMENT_TEXT = "Checkout accepts USD payments only."
PROJECT_KEY = "supervisor-shopflow-v1-project"
SOURCE_KEY = "supervisor-shopflow-v1-scope"
REQUIREMENT_KEY = "supervisor-shopflow-v1-requirement"
BASELINE_KEY = "supervisor-shopflow-v1-baseline"
PARSE_TIMEOUT_SECONDS = 120


class DemoSeedError(RuntimeError):
    pass


class ApiClient(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]: ...


def require_local_url(value: str) -> str:
    parsed = urlsplit(value)
    local_host = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    compose_api = (
        parsed.hostname == "api"
        and parsed.port == 8000
        and os.environ.get("DELIVERYGAP_DEMO_COMPOSE") == "1"
    )
    if (
        parsed.scheme != "http"
        or (not local_host and not compose_api)
        or parsed.port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise DemoSeedError(
            "The demo seeder only accepts an explicit local HTTP API URL, "
            "such as http://localhost:8000 or the isolated Compose API service."
        )
    return value.rstrip("/")


class DemoApi:
    def __init__(self, base_url: str, origin: str) -> None:
        self.client = httpx.Client(base_url=base_url, timeout=15, follow_redirects=False)
        self.origin = origin
        self.csrf_token = ""

    def close(self) -> None:
        self.client.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Origin": self.origin}
        if method not in {"GET", "HEAD"}:
            headers["X-CSRF-Token"] = self.csrf_token
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        response = self.client.request(method, path, json=body, headers=headers)
        if not response.is_success:
            raise DemoSeedError(f"{method} {path} returned HTTP {response.status_code}.")
        if not response.content:
            return {}
        result = response.json()
        if not isinstance(result, dict):
            raise DemoSeedError(f"{method} {path} returned an unexpected response.")
        return result

    def sign_in(self, email: str, password: str) -> None:
        result = self.request(
            "POST",
            "/api/v1/auth/login",
            body={"email": email, "password": password},
        )
        csrf_token = result.get("csrf_token")
        if not isinstance(csrf_token, str) or not csrf_token:
            raise DemoSeedError("The API login response did not include a CSRF token.")
        self.csrf_token = csrf_token


def wait_for_source(api: ApiClient, project_id: str, version_id: str) -> None:
    deadline = time.monotonic() + PARSE_TIMEOUT_SECONDS
    path = f"/api/v1/projects/{project_id}/versions/{version_id}/job"
    while time.monotonic() < deadline:
        job = api.request("GET", path)
        status = job.get("status")
        if status == "succeeded":
            return
        if status == "failed":
            raise DemoSeedError(
                "ShopFlow source processing failed. Check the local worker and retry "
                "the source in the app."
            )
        time.sleep(1)
    raise DemoSeedError("Timed out waiting for ShopFlow source processing. Check the local worker.")


def seed(api: ApiClient) -> None:
    project = api.request(
        "POST",
        "/api/v1/projects",
        body={"name": PROJECT_NAME, "description": PROJECT_DESCRIPTION},
        idempotency_key=PROJECT_KEY,
    )
    project_id = project.get("id")
    if not isinstance(project_id, str) or not project_id:
        raise DemoSeedError("The API did not return the ShopFlow project identity.")

    source = api.request(
        "POST",
        f"/api/v1/projects/{project_id}/documents/manual",
        body={
            "title": "ShopFlow Checkout — fictional scope v1",
            "kind": "scope",
            "text": SCOPE_PATH.read_text(encoding="utf-8"),
        },
        idempotency_key=SOURCE_KEY,
    )
    version_id = source.get("version_id")
    if not isinstance(version_id, str) or not version_id:
        raise DemoSeedError("The API did not return the ShopFlow source version.")
    wait_for_source(api, project_id, version_id)

    spans_result = api.request("GET", f"/api/v1/projects/{project_id}/versions/{version_id}/spans")
    spans = spans_result.get("items")
    if not isinstance(spans, list):
        raise DemoSeedError("The API did not return ShopFlow source passages.")
    matching_spans = [
        span
        for span in spans
        if isinstance(span, dict) and REQUIREMENT_TEXT in str(span.get("text", ""))
    ]
    if len(matching_spans) != 1:
        raise DemoSeedError(
            "Expected exactly one parsed scope passage containing the USD-only requirement."
        )
    span_id = matching_spans[0].get("id")
    if not isinstance(span_id, str) or not span_id:
        raise DemoSeedError("The source passage did not include its canonical identity.")

    created_requirement = api.request(
        "POST",
        f"/api/v1/projects/{project_id}/requirements",
        body={
            "code": "REQ-003",
            "title": REQUIREMENT_TITLE,
            "content": REQUIREMENT_TEXT,
            "source_version_id": version_id,
            "source_span_id": span_id,
            "source_quote": REQUIREMENT_TEXT,
        },
        idempotency_key=REQUIREMENT_KEY,
    )
    requirement_id = created_requirement.get("id")
    if not isinstance(requirement_id, str) or not requirement_id:
        raise DemoSeedError("The API did not return the ShopFlow requirement identity.")
    requirement = api.request(
        "GET",
        f"/api/v1/projects/{project_id}/requirements/{requirement_id}",
    )
    versions = requirement.get("versions")
    if not isinstance(versions, list) or not versions:
        raise DemoSeedError("The API did not return the current ShopFlow requirement version.")
    current_version = next(
        (
            version
            for version in versions
            if isinstance(version, dict) and version.get("version_number") == 1
        ),
        None,
    )
    if not isinstance(current_version, dict):
        raise DemoSeedError("The ShopFlow requirement has no first version.")
    requirement_version_id = current_version.get("id")
    if not isinstance(requirement_version_id, str) or not requirement_version_id:
        raise DemoSeedError("The ShopFlow requirement version has no identity.")

    if current_version.get("status") == "draft":
        api.request(
            "POST",
            f"/api/v1/projects/{project_id}/requirements/{requirement_id}/approve",
            body={"expected_version": 1},
        )
    elif current_version.get("status") != "approved":
        raise DemoSeedError("The ShopFlow requirement is not in an approvable state.")

    baseline = api.request(
        "POST",
        f"/api/v1/projects/{project_id}/baselines",
        body={"requirement_version_ids": [requirement_version_id]},
        idempotency_key=BASELINE_KEY,
    )
    if baseline.get("number") != 1 or len(baseline.get("items", [])) != 1:
        raise DemoSeedError("The API did not create the expected one-item ShopFlow B1.")
    print("ShopFlow demo project is ready with its cited REQ-003 and one-item B1.")


def main() -> None:
    base_url = require_local_url(os.environ.get("DELIVERYGAP_API_URL", "http://localhost:8000"))
    email = os.environ.get("SEED_ADMIN_EMAIL", "admin@deliverygap.example.com")
    password = os.environ.get("SEED_ADMIN_PASSWORD") or getpass.getpass(
        f"Password for local workspace administrator ({email}): "
    )
    if not password:
        raise SystemExit("A local workspace administrator password is required.")
    origin = os.environ.get("APP_ORIGIN", "http://localhost:3000")
    api = DemoApi(base_url, origin)
    try:
        api.sign_in(email, password)
        seed(api)
    finally:
        api.close()


if __name__ == "__main__":
    try:
        main()
    except (DemoSeedError, httpx.HTTPError, OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
