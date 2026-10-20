# Disposable infrastructure acceptance

The Q01 harness uses real PostgreSQL, Redis, MinIO, and fork-based RQ workers with synthetic documents. It is separate from the development stack, publishes no host ports, mounts no host directories, and supplies only disposable test credentials. Do not point it at shared services: the Redis outage test temporarily pauses **all** commands on its Redis instance.

## Run

With Docker and Compose available (Linux containers on Windows), run from the repository root:

```sh
docker compose -f compose.acceptance.yaml up --build --abort-on-container-exit --exit-code-from acceptance
docker compose -f compose.acceptance.yaml down --volumes --remove-orphans
```

Record the first command's exit status before cleanup. A zero exit status is the acceptance result; cleanup succeeding does not mean tests passed. The dedicated CI job preserves this distinction and always tears down its services. It has a 15-minute deadline.

The image installs the frozen Python lock, includes no environment files, and runs as a non-root user. Each test creates its own PostgreSQL schema and Redis queue. The PostgreSQL test image initializes pgvector in `deliverygap_test_extensions`; test search paths include that namespace but exclude `public` so application tables cannot be resolved accidentally. The storage bucket contains synthetic objects and is discarded with the stack. No application database or development volume is used.

## Checks

- Upload through the authenticated API to real private object storage; verify exact original bytes, conditional overwrite rejection, and anonymous download denial.
- Pause Redis after the upload/outbox transaction commits. Check that unsuccessful dispatch does not record delivery; resume Redis and execute the persisted job using a real RQ worker.
- Deliver the completed job again through RQ and verify one attempt and one source span.
- Pause a worker after it reads the actual S3 original, with its running attempt already committed. Kill the RQ parent and its separate work-horse process group.
- Verify no output was committed, expire the persisted lease, reconcile the lost attempt, and run a replacement worker. Verify the old attempt is marked lost, the new fence succeeds, and another delivery creates no duplicate spans.
- Remove a disposable synthetic object, exhaust three real-worker parsing attempts, restore its original bytes, and recover through the explicit retry API without duplicate output.
- Kill import and report workers after flushing output but before transaction commit. Verify PostgreSQL rolls back the output and a replacement RQ delivery commits exactly one artifact or report snapshot.

The test-only pause wraps storage reads; parsing, outbox dispatch, authorization, persistence, and fencing use production code. Tests advance persisted lease/backoff timestamps to avoid waiting the production 180-second lease. This verifies expiry handling, not wall-clock scheduling accuracy. `CLIENT PAUSE` verifies an actual Redis command timeout, not Redis process restart or data-loss recovery.

## Limits and acceptance status

Ordinary backend runs skip the five opt-in cases. Enabling them requires Linux and PostgreSQL; they fail rather than falling back to SQLite or in-memory storage. The existing CI verification job separately exercises Alembic migration round trips. This harness uses the test fixture's schema creation and does not itself prove clean production migration/startup.

The initial implementation was checked locally for lint, formatting, test collection, and existing backend regressions. Docker is unavailable on that host, so **the real-service tests have not yet been run**. A passing dedicated CI run is required before recording infrastructure acceptance.

For other PostgreSQL test databases, an administrator must first provision [the test extension namespace](../infrastructure/test-extensions.sql). Do not apply this to a shared database without approval. The fixture fails before creating a schema when the prerequisite is absent and cleans up its owned schema even if later setup fails. Existing vector extensions in a different namespace are not moved automatically.

Remaining harness coverage includes S3 service interruption and provider-worker recovery for extraction/analysis. Import/report recovery currently tests direct RQ redelivery, not a killed dispatch process. All five live cases still need execution. Clean full-stack startup, backup/restore rehearsal, live provider evaluation, and release performance/accessibility checks remain separate gates.
