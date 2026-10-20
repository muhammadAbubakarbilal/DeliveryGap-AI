---
name: background-jobs-engineer
description: Design durable Redis/RQ processing, outbox dispatch, leases, retries, checkpoints, and idempotent jobs for DeliveryGap AI.
---

## Activate when

Implementing parsing, embeddings, model inference, imports, reports, retries, recovery, or any work that can outlive an HTTP request.

## Responsibilities

- Keep DB state and queue delivery recoverable through transactional outbox behavior.
- Use stable job IDs, leases/fencing, bounded retries, checkpoints, and idempotent outputs.
- Recheck project authorization before work and commits.

## Procedure

1. Define job states, attempt limits, retryable/non-retryable errors, and ownership.
2. Persist operation/job/outbox records in one transaction.
3. Dispatch stable IDs, acquire fenced attempts, checkpoint stages, and commit only current attempts.
4. Reconcile undispatched/expired work and expose explicit retry/failure diagnostics.

## Required checks

- Duplicate delivery, worker death, Redis outage, stale lease, timeout, and retry exhaustion.
- No duplicate drafts, findings, proposals, or reports.
- Safe operational errors without source text or secrets.

## Completion criteria

Jobs recover deterministically, preserve history, enforce scope, and have operational tests for failure and duplicate paths.
