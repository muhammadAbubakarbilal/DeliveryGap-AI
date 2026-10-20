"""Disposable synthetic API for Playwright. Never seeds the configured application DB.

Uses a new PostgreSQL schema when TEST_DATABASE_URL is set; otherwise an explicitly
temporary SQLite database for browser/API wiring checks only.
"""

import os
import sys
import tempfile
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps" / "api"))
os.chdir(root)
os.environ["APP_ORIGIN"] = "http://127.0.0.1:3100"
os.environ["COOKIE_SECURE"] = "false"
os.environ["DATABASE_URL_UNPOOLED"] = ""
os.environ["NEON_AUTH_BASE_URL"] = ""
os.environ["NEON_AUTH_JWKS_URL"] = ""
temporary = tempfile.TemporaryDirectory(prefix="deliverygap-smoke-")
postgres_url = os.environ.get("TEST_DATABASE_URL")
schema = "smoke_" + uuid4().hex
if postgres_url:
    admin_engine = create_engine(postgres_url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    os.environ["DATABASE_URL"] = (
        make_url(postgres_url)
        .update_query_dict({"options": f"-csearch_path={schema},deliverygap_test_extensions"})
        .render_as_string(hide_password=False)
    )
else:
    os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(temporary.name) / "smoke.db")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.models import Member, Project, User  # noqa: E402
from app.security import hasher  # noqa: E402

command.upgrade(Config(str(root / "alembic.ini")), "head")
with SessionLocal() as db:
    admin = User(
        email="admin@example.com",
        display_name="Alex Morgan",
        is_admin=True,
        password_hash=hasher.hash("smoke-only-password"),
    )
    reviewer = User(
        email="reviewer@example.com",
        display_name="Sam Rivera",
        password_hash=hasher.hash("smoke-only-password"),
    )
    db.add_all([admin, reviewer])
    db.flush()
    project = Project(
        name="ShopFlow Checkout",
        description="A synthetic checkout project for scope and delivery review.",
        owner_id=admin.id,
    )
    db.add(project)
    db.flush()
    db.add_all(
        [
            Member(project_id=project.id, user_id=admin.id, role="lead"),
            Member(project_id=project.id, user_id=reviewer.id, role="reviewer"),
        ]
    )
    db.commit()

from app.main import app  # noqa: E402
from app.source_jobs import run_parse  # noqa: E402
from app.source_storage import get_storage  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class SmokeStorage:
    """In-memory private storage exclusively for this disposable browser fixture."""

    def __init__(self):
        self.data = {}

    def put(self, key, content):
        if key in self.data:
            raise ValueError("Original already exists")
        self.data[key] = content

    def get(self, key):
        return self.data[key]


storage = SmokeStorage()
app.dependency_overrides[get_storage] = lambda: storage
with TestClient(app, headers={"origin": "http://127.0.0.1:3100"}) as client:
    session = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@example.com",
            "password": "smoke-only-password",
        },
    )
    session.raise_for_status()
    source = client.post(
        f"/api/v1/projects/{project.id}/documents/manual",
        json={"title": "Synthetic currency scope", "text": "Checkout accepts USD payments only."},
        headers={"X-CSRF-Token": session.json()["csrf_token"], "Idempotency-Key": str(uuid4())},
    )
    source.raise_for_status()
    run_parse(SessionLocal, storage, source.json()["job_id"])


from app.extraction import run_extraction  # noqa: E402
from app.grounded_analysis import DECOMPOSITION_PROMPT, run_analysis  # noqa: E402
from app.operation_jobs import execute_with  # noqa: E402
from app.operation_models import Operation  # noqa: E402
from app.source_models import ParseJob  # noqa: E402
from sqlalchemy import select  # noqa: E402

# Test-only executor exercises durable DB commands without pretending to test Redis/RQ.
stop_jobs = Event()


def fixture_extraction(prompt):
    import json

    spans = json.loads(prompt.split("SOURCE PASSAGES:\n", 1)[1])
    if len(spans) != 1 or spans[0]["text"] != "Checkout accepts USD payments only.":
        raise ValueError("Unknown synthetic extraction fixture")
    return json.dumps(
        {
            "requirements": [
                {
                    "title": "Extracted currency proposal",
                    "content": spans[0]["text"],
                    "span_id": spans[0]["id"],
                    "quote": spans[0]["text"],
                }
            ]
        }
    )


def fixture_analysis(prompt):
    import json

    if prompt.startswith(DECOMPOSITION_PROMPT):
        data = json.loads(prompt[len(DECOMPOSITION_PROMPT) :])
        request = data["request"]
        if request == "Add EUR and GBP checkout.":
            return json.dumps({"requests": [{"start": 0, "end": len(request), "text": request}]})
        if request == "Add EUR and GBP checkout. Also allow guest checkout.":
            first = "Add EUR and GBP checkout."
            second = "Also allow guest checkout."
            return json.dumps(
                {
                    "requests": [
                        {"start": 0, "end": len(first), "text": first},
                        {
                            "start": len(first) + 1,
                            "end": len(first) + 1 + len(second),
                            "text": second,
                        },
                    ]
                }
            )
        if request == "Let's schedule a call next Tuesday.":
            return json.dumps({"requests": []})
        raise ValueError("Unknown synthetic analysis fixture")

    data = json.loads(prompt[prompt.index('{"request":') :])
    if data["request"] == "Also allow guest checkout.":
        raise ValueError("Synthetic per-request failure")
    if (
        data["request"] != "Add EUR and GBP checkout."
        or len(data["evidence"]) != 1
        or data["evidence"][0]["source_quote"] != "Checkout accepts USD payments only."
    ):
        raise ValueError("Unknown synthetic analysis fixture")
    return json.dumps(
        {
            "findings": [
                {
                    "classification": "CONFLICT",
                    "summary": "Synthetic grounded proposal for browser testing.",
                    "input_quote": data["request"],
                    "requirement_version_id": data["evidence"][0]["id"],
                    "evidence_quote": data["evidence"][0]["source_quote"],
                }
            ]
        }
    )


def fixture_embeddings(inputs):
    return [[1.0, *([0.0] * 1023)] for _ in inputs]


def execute_smoke_jobs():
    while not stop_jobs.wait(0.2):
        with SessionLocal() as db:
            parse_ids = list(db.scalars(select(ParseJob.id).where(ParseJob.status == "queued")))
            operation_ids = list(
                db.execute(select(Operation.id, Operation.kind).where(Operation.status == "queued"))
            )
        for job_id in parse_ids:
            run_parse(SessionLocal, storage, job_id)
        for operation_id, kind in operation_ids:
            if kind == "extraction":
                run_extraction(SessionLocal, operation_id, fixture_extraction)
            elif kind == "analysis":
                run_analysis(SessionLocal, operation_id, fixture_analysis, fixture_embeddings)
            else:
                execute_with(SessionLocal, operation_id)


job_thread = Thread(target=execute_smoke_jobs, daemon=True)
job_thread.start()

try:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, access_log=False)
finally:
    stop_jobs.set()
    job_thread.join(timeout=10)
    engine.dispose()
    temporary.cleanup()
    if postgres_url:
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()
