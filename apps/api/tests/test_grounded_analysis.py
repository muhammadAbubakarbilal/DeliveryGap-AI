import json
from uuid import uuid4

import pytest
from app.ai_gateway import GatewayUnavailable
from app.grounded_analysis import (
    DECOMPOSITION_PROMPT,
    decompose_request,
    fuse_candidates,
    run_analysis,
)
from app.operation_models import Operation
from test_operations import baseline, post


def authorized_baseline(client, login, database):
    base, saved = baseline(client, login, database)
    consent = client.patch(base + "/ai-consent", json={"enabled": True})
    assert consent.status_code == 200, consent.text
    return base, saved


def fixed_embeddings(inputs):
    return [[1.0, *([0.0] * 1023)] for _ in inputs]


def queued(client, base, saved, text="Add EUR and GBP checkout.", key=None):
    return post(
        client,
        base + "/analysis-jobs",
        {
            "baseline_id": saved["id"],
            "input_text": text,
        },
        key,
    )


def provider_output(prompt, invalid=False):
    if prompt.startswith(DECOMPOSITION_PROMPT):
        data = json.loads(prompt[len(DECOMPOSITION_PROMPT) :])
        text = data["request"]
        return json.dumps({"requests": [{"start": 0, "end": len(text), "text": text}]})
    data = json.loads(prompt[prompt.index('{"request":') :])
    return json.dumps(
        {
            "findings": [
                {
                    "classification": "CONFLICT",
                    "summary": "Currency condition conflicts; review required.",
                    "input_quote": data["request"],
                    "requirement_version_id": data["evidence"][0]["id"],
                    "evidence_quote": "invented"
                    if invalid
                    else data["evidence"][0]["source_quote"],
                }
            ]
        }
    )


@pytest.mark.parametrize("invalid", [False, True])
def test_grounded_analysis_citations_replay_and_isolation(client, login, database, invalid):
    base, saved = authorized_baseline(client, login, database)
    key = str(uuid4())
    response = queued(client, base, saved, key=key)
    assert response.status_code == 202, response.text
    assert queued(client, base, saved, key=key).json() == response.json()
    operation_id = response.json()["id"]
    calls = []

    def provider(prompt):
        calls.append(prompt)
        return provider_output(prompt, invalid)

    embedded_batches = []

    def embedder(inputs):
        embedded_batches.append(inputs)
        return fixed_embeddings(inputs)

    run_analysis(database, operation_id, provider, embedder)
    run_analysis(database, operation_id, provider, embedder)
    assert len(calls) == 2
    assert len(embedded_batches) == 1
    assert len(embedded_batches[0]) == 2
    op = client.get(base + f"/operations/{operation_id}").json()
    assert op["status"] == "succeeded", op
    assert op["result"]["retrieval_method"] == "bm25+qwen3-embedding-rrf-v1"
    assert op["result"]["retrieval_candidates"][0]["fused_rank"] == 1
    assert op["result"]["retrieval_candidates"][0]["semantic_rank"] == 1
    run = client.get(base + f"/analysis/{op['result']['run_id']}").json()
    finding = run["findings"][0]
    assert run["provider"] == "neon-hybrid"
    assert finding["classification"] == ("INSUFFICIENT_EVIDENCE" if invalid else "CONFLICT")
    assert finding["input_quote"] == "Add EUR and GBP checkout."
    assert finding["review_status"] == "pending"
    if invalid:
        assert finding["evidence_quote"] is None
    second = queued(client, base, saved, text="Add AUD checkout.").json()
    run_analysis(database, second["id"], provider, embedder)
    assert len(embedded_batches) == 2
    assert len(embedded_batches[1]) == 1
    assert len(calls) == 4
    login("outsider")
    assert queued(client, base, saved).status_code == 404
    assert client.get(base + f"/analysis/{run['id']}").status_code == 404


def test_dense_retrieval_can_find_candidates_without_lexical_overlap(client, login, database):
    base, saved = authorized_baseline(client, login, database)
    op = queued(client, base, saved, text="Aeronautical telemetry").json()

    def abstain(prompt):
        if prompt.startswith(DECOMPOSITION_PROMPT):
            data = json.loads(prompt[len(DECOMPOSITION_PROMPT) :])
            text = data["request"]
            return json.dumps({"requests": [{"start": 0, "end": len(text), "text": text}]})
        data = json.loads(prompt[prompt.index('{"request":') :])
        return json.dumps(
            {
                "findings": [
                    {
                        "classification": "INSUFFICIENT_EVIDENCE",
                        "summary": "The retrieved passage does not establish this request.",
                        "input_quote": data["request"],
                        "requirement_version_id": None,
                        "evidence_quote": None,
                    }
                ]
            }
        )

    run_analysis(database, op["id"], abstain, fixed_embeddings)
    run = client.get(base + "/analysis").json()[0]
    assert run["findings"][0]["classification"] == "INSUFFICIENT_EVIDENCE"
    operation = client.get(base + f"/operations/{op['id']}").json()
    candidate = operation["result"]["retrieval_candidates"][0]
    assert candidate["bm25_score"] is None
    assert candidate["semantic_rank"] == 1


def test_hybrid_fusion_preserves_distinct_rank_diagnostics():
    documents = [
        {"id": "lexical", "text": "payment authorization"},
        {"id": "semantic", "text": "unrelated phrase"},
    ]
    ranked = fuse_candidates(
        documents,
        "payment authorization",
        [1.0, 0.0],
        {"lexical": [0.0, 1.0], "semantic": [1.0, 0.0]},
    )
    assert ranked[0]["id"] == "lexical"
    assert ranked[0]["lexical_rank"] == 1
    assert ranked[0]["semantic_rank"] == 2
    assert ranked[1]["id"] == "semantic"
    assert ranked[1]["lexical_rank"] is None
    assert ranked[1]["semantic_rank"] == 1


def test_cancel_and_foreign_baseline(client, login, database):
    base, saved = authorized_baseline(client, login, database)
    other_base, _ = authorized_baseline(client, login, database)
    assert queued(client, other_base, saved).status_code == 404
    op = queued(client, base, saved).json()

    def cancel(prompt):
        assert client.post(base + f"/operations/{op['id']}/cancel").status_code == 200
        return provider_output(prompt)

    run_analysis(database, op["id"], cancel, fixed_embeddings)
    assert client.get(base + "/analysis").json() == []
    with database() as db:
        assert db.get(Operation, op["id"]).status == "cancelled"

    stopped = queued(client, base, saved).json()

    def cancel_during_embedding(inputs):
        assert client.post(base + f"/operations/{stopped['id']}/cancel").status_code == 200
        return fixed_embeddings(inputs)

    run_analysis(
        database,
        stopped["id"],
        provider_output,
        cancel_during_embedding,
    )
    assert client.get(base + f"/operations/{stopped['id']}").json()["status"] == "cancelled"


def test_invalid_embedding_response_fails_without_calling_completion(client, login, database):
    base, saved = authorized_baseline(client, login, database)
    op = queued(client, base, saved).json()
    run_analysis(
        database,
        op["id"],
        provider_output,
        lambda inputs: [[0.0]],
    )
    result = client.get(base + f"/operations/{op['id']}").json()
    assert result["status"] == "failed"
    assert result["error"] == "Analysis output unavailable or invalid; no findings saved"


def test_multi_request_analysis_persists_unicode_spans_and_partial_results(client, login, database):
    base, saved = authorized_baseline(client, login, database)
    text = "🙂 Add EUR and GBP checkout. Also allow guest checkout."
    first = "Add EUR and GBP checkout."
    second = "Also allow guest checkout."
    first_start = text.index(first)

    def partial_provider(prompt):
        if prompt.startswith(DECOMPOSITION_PROMPT):
            return json.dumps(
                {
                    "requests": [
                        {
                            "start": first_start,
                            "end": first_start + len(first),
                            "text": first,
                        },
                        {
                            "start": text.index(second),
                            "end": text.index(second) + len(second),
                            "text": second,
                        },
                    ]
                }
            )
        data = json.loads(prompt[prompt.index('{"request":') :])
        if data["request"] == second:
            raise GatewayUnavailable("Synthetic request failure")
        return provider_output(prompt)

    operation = queued(client, base, saved, text=text).json()
    run_analysis(database, operation["id"], partial_provider, fixed_embeddings)
    result = client.get(base + f"/operations/{operation['id']}").json()
    assert result["status"] == "succeeded"
    assert result["result"]["outcome"] == "partial"
    assert [segment["status"] for segment in result["result"]["request_segments"]] == [
        "completed",
        "failed",
    ]
    run = client.get(base + f"/analysis/{result['result']['run_id']}").json()
    assert run["outcome"] == "partial"
    assert len(run["findings"]) == 1
    finding = run["findings"][0]
    assert finding["request_index"] == 0
    assert finding["input_quote"] == first
    assert finding["input_span_start"] == first_start
    assert finding["input_span_end"] == first_start + len(first)


def test_non_actionable_request_succeeds_without_findings_or_embeddings(client, login, database):
    base, saved = authorized_baseline(client, login, database)
    text = "Let's schedule a call next Tuesday and share the status update."
    operation = queued(client, base, saved, text=text).json()
    calls = []

    def no_actionable(prompt):
        calls.append(prompt)
        assert prompt.startswith(DECOMPOSITION_PROMPT)
        return json.dumps({"requests": []})

    def no_embeddings(inputs):
        pytest.fail("Non-actionable text must not be embedded")

    run_analysis(database, operation["id"], no_actionable, no_embeddings)
    saved_operation = client.get(base + f"/operations/{operation['id']}").json()
    assert saved_operation["status"] == "succeeded"
    assert saved_operation["result"]["outcome"] == "no_actionable_requests"
    assert "No actionable" in saved_operation["result"]["message"]
    run = client.get(base + f"/analysis/{saved_operation['result']['run_id']}").json()
    assert run["outcome"] == "no_actionable_requests"
    assert run["findings"] == []
    assert len(calls) == 1


def test_overlapping_or_unfaithful_request_spans_fail_closed(client, login, database):
    base, saved = authorized_baseline(client, login, database)
    text = "Add EUR checkout. Add GBP checkout."
    operation = queued(client, base, saved, text=text).json()
    invalid = json.dumps(
        {
            "requests": [
                {"start": 0, "end": 17, "text": "Add EUR checkout."},
                {"start": 10, "end": len(text), "text": text[10:]},
            ]
        }
    )
    run_analysis(database, operation["id"], lambda _: invalid, fixed_embeddings)
    saved_operation = client.get(base + f"/operations/{operation['id']}").json()
    assert saved_operation["status"] == "failed"
    assert saved_operation["error"] == "Analysis output unavailable or invalid; no findings saved"


def test_decomposition_enforces_ten_request_limit():
    text = "abcdefghijk"
    response = json.dumps(
        {
            "requests": [
                {"start": index, "end": index + 1, "text": text[index : index + 1]}
                for index in range(11)
            ]
        }
    )
    with pytest.raises(ValueError):
        decompose_request(text, lambda _: response, lambda: True)


def test_analysis_requires_consent_and_worker_rechecks_revocation(client, login, database):
    base, saved = baseline(client, login, database)
    assert queued(client, base, saved).status_code == 409
    assert client.patch(base + "/ai-consent", json={"enabled": True}).status_code == 200
    operation = queued(client, base, saved).json()
    assert client.patch(base + "/ai-consent", json={"enabled": False}).status_code == 200
    run_analysis(
        database,
        operation["id"],
        lambda _: pytest.fail("Revoked consent must prevent completion calls"),
        lambda _: pytest.fail("Revoked consent must prevent embedding calls"),
    )
    result = client.get(base + f"/operations/{operation['id']}").json()
    assert result["status"] == "failed"
    assert "consent" in result["error"]


def test_failed_analysis_can_be_retried_once_idempotently(client, login, database):
    base, saved = authorized_baseline(client, login, database)
    operation = queued(client, base, saved).json()
    run_analysis(
        database,
        operation["id"],
        lambda _: (_ for _ in ()).throw(GatewayUnavailable("Temporary synthetic outage")),
        fixed_embeddings,
    )
    failed = client.get(base + f"/operations/{operation['id']}").json()
    assert failed["status"] == "failed"
    assert failed["attempts"] == 1

    retry_key = str(uuid4())
    retry_url = base + f"/operations/{operation['id']}/retry"
    retried = client.post(
        retry_url,
        json={},
        headers={"Idempotency-Key": retry_key},
    )
    assert retried.status_code == 202, retried.text
    assert retried.json()["status"] == "queued"
    assert (
        client.post(retry_url, json={}, headers={"Idempotency-Key": retry_key}).json()
        == retried.json()
    )

    calls = []

    def recovered_provider(prompt):
        calls.append(prompt)
        return provider_output(prompt)

    run_analysis(database, operation["id"], recovered_provider, fixed_embeddings)
    run_analysis(
        database,
        operation["id"],
        lambda _: pytest.fail("Duplicate delivery after success must not call the provider"),
        fixed_embeddings,
    )
    assert len(calls) == 2
    assert len(client.get(base + "/analysis").json()) == 1
    assert client.get(base + f"/operations/{operation['id']}").json()["status"] == "succeeded"
    assert (
        client.post(retry_url, json={}, headers={"Idempotency-Key": retry_key}).json()
        == retried.json()
    )


def test_retry_enforces_project_consent_membership_and_attempt_limit(client, login, database):
    base, saved = baseline(client, login, database)
    assert client.patch(base + "/ai-consent", json={"enabled": True}).status_code == 200
    queued_operation = queued(client, base, saved).json()
    assert (
        client.post(
            base + f"/operations/{queued_operation['id']}/retry",
            json={},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 409
    )
    operation = queued(client, base, saved).json()
    run_analysis(
        database,
        operation["id"],
        lambda _: (_ for _ in ()).throw(GatewayUnavailable("Temporary synthetic outage")),
        fixed_embeddings,
    )
    retry_url = base + f"/operations/{operation['id']}/retry"
    assert client.patch(base + "/ai-consent", json={"enabled": False}).status_code == 200
    assert (
        client.post(retry_url, json={}, headers={"Idempotency-Key": str(uuid4())}).status_code
        == 409
    )
    assert (
        client.post(
            base + "/members",
            json={"email": "reviewer@example.com", "role": "reviewer"},
        ).status_code
        == 201
    )
    login("reviewer")
    assert (
        client.post(retry_url, json={}, headers={"Idempotency-Key": str(uuid4())}).status_code
        == 403
    )
    login("outsider")
    assert (
        client.post(retry_url, json={}, headers={"Idempotency-Key": str(uuid4())}).status_code
        == 404
    )

    login()
    assert client.patch(base + "/ai-consent", json={"enabled": True}).status_code == 200
    with database() as db:
        saved_operation = db.get(Operation, operation["id"])
        saved_operation.attempts = 3
        db.commit()
    assert (
        client.post(retry_url, json={}, headers={"Idempotency-Key": str(uuid4())}).status_code
        == 409
    )
