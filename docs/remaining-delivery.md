# Remaining delivery implementation

The PRD and implementation plan remain authoritative. This continuation closes provenance gaps first, then adds CSV imports and frozen exports as complete vertical slices. Automated extraction and grounded provider analysis follow; release acceptance remains open until real infrastructure and human-reviewed evaluations are available.

## Actors and acceptance

- Contributors may preview and commit bounded task/test CSVs in active projects. Reviewers may only inspect results. Import references create proposals; only leads explicitly accept them.
- Preview records row-level validation errors, normalized values, duplicate IDs, selected baseline, and the artifact revisions observed. Commit is a durable command executed outside the request. Changed artifacts since preview require another preview. Identical reimports preserve artifact revision numbers.
- CSV maximum: 500 rows and 1 MB of UTF-8 text. Timestamps must include a timezone. Both requirement aliases are accepted, contradictory aliases rejected. URLs must use HTTP(S).
- Source originals/spans/chunks are protected from update/delete by database guards. Accepted evidence records its inspected artifact revision; later changes are visibly stale.
- Reports freeze a selected published baseline, requirement citations, findings and decision states, artifact revisions and link states. Markdown and CSV download the same immutable payload. Missing evidence is never described as missing implementation.
- Every command rechecks project access, carries an idempotency key, and writes audit records. Background work rechecks its actor's access before committing. Lost queue deliveries are redispatched; duplicates cannot duplicate results.

## Dependencies and risks

Neon PostgreSQL is available. Docker is not installed; real Redis/S3/Linux-worker verification is blocked pending installation or hosted service configuration. Neon AI Gateway remains blocked by the Free plan. Synthetic tests are not provider-quality evaluation or proof of real queue recovery. Existing user projects are preserved.
