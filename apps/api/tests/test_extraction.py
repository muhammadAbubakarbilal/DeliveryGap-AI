import json
from datetime import timedelta
from uuid import uuid4

import pytest
from app.extraction import run_extraction, source_batches
from app.models import now
from app.operation_models import Operation
from fastapi import HTTPException
from test_scope_integrity import grounded


def prepared(client, login, database):
    base, body = grounded(client, login, database)
    consent = client.patch(base + "/ai-consent", json={"enabled": True})
    assert consent.status_code == 200, consent.text
    return base, body


def queue(client, base, body, key=None):
    return client.post(
        base + "/requirements/extract",
        json={"source_version_id": body["source_version_id"]},
        headers={"Idempotency-Key": key or str(uuid4())},
    )


def result(body):
    return json.dumps(
        {
            "requirements": [
                {
                    "title": "Currency",
                    "content": "USD only checkout",
                    "span_id": body["source_span_id"],
                    "quote": body["source_quote"],
                }
            ]
        }
    )


def test_extraction_exact_citations_drafts_and_duplicate_delivery(client, login, database):
    base, body = prepared(client, login, database)
    key = str(uuid4())
    response = queue(client, base, body, key)
    assert response.status_code == 202, response.text
    assert queue(client, base, body, key).json() == response.json()
    calls = []

    def provider(prompt):
        calls.append(prompt)
        return result(body)

    run_extraction(database, response.json()["id"], provider)
    run_extraction(database, response.json()["id"], provider)
    assert len(calls) == 1
    drafts = client.get(base + "/requirements").json()["items"]
    assert len(drafts) == 1
    assert drafts[0]["versions"][0]["status"] == "draft"
    assert drafts[0]["versions"][0]["source_quote"] == body["source_quote"]
    login("outsider")
    assert queue(client, base, body).status_code == 404


def test_invalid_quote_and_cancelled_attempt_save_no_drafts(client, login, database):
    base, body = prepared(client, login, database)
    first = queue(client, base, body).json()
    run_extraction(database, first["id"], lambda _: result({**body, "source_quote": "invented"}))
    assert client.get(base + f"/operations/{first['id']}").json()["status"] == "failed"
    second = queue(client, base, body).json()

    def cancel_then_return(_):
        assert client.post(base + f"/operations/{second['id']}/cancel").status_code == 200
        return result(body)

    run_extraction(database, second["id"], cancel_then_return)
    assert client.get(base + f"/operations/{second['id']}").json()["status"] == "cancelled"
    assert client.get(base + "/requirements").json()["total"] == 0


def test_batch_bounds_unicode_and_overlap():
    text = "😀" * 2500
    batches = source_batches([{"id": str(uuid4()), "text": text}])
    assert all(len(json.dumps(batch, ensure_ascii=True)) <= 16000 for batch in batches)
    passages = [p for batch in batches for p in batch]
    assert passages[0]["text"][-200:] == passages[1]["text"][:200]
    with pytest.raises(HTTPException):
        source_batches([{"id": str(uuid4()), "text": "x" * 500000}])


def test_checkpoint_resumes_and_publishes_once(client, login, database):
    base, body = prepared(client, login, database)
    operation_id = queue(client, base, body).json()["id"]
    # Two overlapping batches exercise restart/deduplication without mutating source originals.
    with database() as db:
        operation = db.get(Operation, operation_id)
        payload = dict(operation.payload)
        payload["batches"] = payload["batches"] * 2
        operation.payload = payload
        db.commit()
    run_extraction(database, operation_id, lambda _: result(body))
    checkpoint = client.get(base + f"/operations/{operation_id}").json()
    assert checkpoint["status"] == "queued"
    assert checkpoint["result"]["batches_completed"] == 1
    assert client.get(base + "/requirements").json()["total"] == 0
    run_extraction(database, operation_id, lambda _: result(body))
    run_extraction(database, operation_id, lambda _: pytest.fail("Repeated finished work"))
    assert client.get(base + "/requirements").json()["total"] == 1
    completed = client.get(base + f"/operations/{operation_id}").json()
    assert completed["result"]["batches_completed"] == 2
    assert "proposals" not in completed["result"]


def test_later_batch_failure_leaves_no_partial_drafts(client, login, database):
    base, body = prepared(client, login, database)
    operation_id = queue(client, base, body).json()["id"]
    with database() as db:
        operation = db.get(Operation, operation_id)
        operation.payload = {**operation.payload, "batches": operation.payload["batches"] * 2}
        db.commit()
    run_extraction(database, operation_id, lambda _: result(body))
    run_extraction(database, operation_id, lambda _: result({**body, "source_quote": "invented"}))
    failed = client.get(base + f"/operations/{operation_id}").json()
    assert failed["status"] == "failed"
    assert failed["result"]["batches_completed"] == 1
    assert len(failed["result"]["proposals"]) == 1
    assert client.get(base + "/requirements").json()["total"] == 0
    retry_key = str(uuid4())
    retry = client.post(
        base + f"/operations/{operation_id}/retry",
        json={},
        headers={"Idempotency-Key": retry_key},
    )
    assert retry.status_code == 202, retry.text
    assert retry.json()["status"] == "queued"
    assert (
        client.post(
            base + f"/operations/{operation_id}/retry",
            json={},
            headers={"Idempotency-Key": retry_key},
        ).json()
        == retry.json()
    )
    run_extraction(database, operation_id, lambda _: result(body))
    run_extraction(database, operation_id, lambda _: pytest.fail("Completed retry must be a no-op"))
    completed = client.get(base + f"/operations/{operation_id}").json()
    assert completed["status"] == "succeeded"
    assert completed["result"]["batches_completed"] == 2
    assert client.get(base + "/requirements").json()["total"] == 1


def test_dispatch_skips_leased_work_and_recovers_checkpoint(client, login, database, monkeypatch):
    from app import operation_jobs

    base, body = prepared(client, login, database)
    operation_id = queue(client, base, body).json()["id"]
    with database() as db:
        operation = db.get(Operation, operation_id)
        operation.payload = {**operation.payload, "batches": operation.payload["batches"] * 2}
        for _ in range(26):
            db.add(
                Operation(
                    project_id=operation.project_id,
                    actor_id=operation.actor_id,
                    kind="extraction",
                    status="running",
                    payload={},
                    lease_until=now() + timedelta(minutes=5),
                    created_at=now() - timedelta(days=1),
                )
            )
        db.commit()
    run_extraction(database, operation_id, lambda _: result(body))
    with database() as db:
        operation = db.get(Operation, operation_id)
        operation.status = "running"
        operation.fence = "lost-worker"
        operation.attempts = 1
        operation.lease_until = now() - timedelta(seconds=1)
        db.commit()
    sent = []

    class FakeQueue:
        def __init__(self, *args, **kwargs):
            pass

        def enqueue(self, function, identifier, **kwargs):
            sent.append(identifier)

    monkeypatch.setattr(operation_jobs, "SessionLocal", database)
    monkeypatch.setattr(operation_jobs, "Queue", FakeQueue)
    operation_jobs.dispatch_operations()
    assert sent == [operation_id]
    run_extraction(database, operation_id, lambda _: result(body))
    final = client.get(base + f"/operations/{operation_id}").json()
    assert final["status"] == "succeeded"
    assert final["error"] is None
    assert final["result"]["batches_completed"] == 2
    assert client.get(base + "/requirements").json()["total"] == 1


def test_extraction_requires_consent_and_worker_rechecks_revocation(client, login, database):
    base, body = grounded(client, login, database)
    denied = queue(client, base, body)
    assert denied.status_code == 409
    assert client.patch(base + "/ai-consent", json={"enabled": True}).status_code == 200
    operation_id = queue(client, base, body).json()["id"]
    assert client.patch(base + "/ai-consent", json={"enabled": False}).status_code == 200
    run_extraction(
        database,
        operation_id,
        lambda _: pytest.fail("Revoked consent must prevent external provider calls"),
    )
    operation = client.get(base + f"/operations/{operation_id}").json()
    assert operation["status"] == "failed"
    assert "consent" in operation["error"]
