# Local deployment and release rehearsal

This is the procedure to exercise the implemented product, not a release acceptance certificate. Record actual results in [completion work](completion-work.md). The [implementation plan](../IMPLEMENTATION_PLAN.md) defines the release gates.

## Start the full local stack

Prerequisites: Docker with Linux containers and Compose, an unused local port set (3000, 8000, 5432, 6379, 9000, 9001), and sufficient disk space for images/data. Use an isolated checkout for a clean rehearsal.

1. Copy `.env.example` to `.env`. Set unique database/storage passwords and a seed administrator password of at least 12 characters. Keep this file out of source control. The local Compose stack uses its own PostgreSQL database and local authentication; existing Neon accounts are not copied.
2. Run from the repository root:

   ```sh
   docker compose up --build -d
   docker compose --profile tools run --rm seed
   docker compose --profile tools run --rm seed
   docker compose ps --all
   ```

3. Confirm the second seed says the account already exists, the migration/storage initialization containers exited successfully, API readiness succeeds at `http://localhost:8000/api/v1/health/ready`, and the web app opens at `http://localhost:3000`. Worker and dispatcher must remain running.
4. Sign in with the seeded account and perform the synthetic walkthrough below. Never treat API readiness alone as proof of worker health.
5. Stop and restart the stack without deleting volumes; verify the account, sources, baselines, decisions, and report snapshots persist.

For live analysis, set `NEON_AI_GATEWAY_BASE_URL`, `NEON_AI_GATEWAY_TOKEN`, and optionally `NEON_EMBEDDING_MODEL` in the Compose environment file, then recreate API/worker/dispatcher services. These values are passed only to backend services. A valid provider account and budget are required. Project-lead consent must still be enabled in the UI. The local synthetic replay does not require live provider access.

## Synthetic demonstration (target: 7–10 minutes)

1. Create a project. Upload a UTF-8 text file containing exactly `Checkout accepts USD payments only.` Verify the parsed passage and original download.
2. Create a grounded requirement with that exact content and source quote, approve it, and publish B1 containing only this requirement.
3. Open analysis and use the explicitly labeled synthetic fixture with exactly `Add EUR and GBP checkout.` Inspect its source citation and record a human decision. Explain that this is a fixed workflow demonstration, not live model evaluation.
4. On delivery evidence, preview a task CSV using the downloaded template; commit it and verify repeat import does not duplicate the artifact. Create test evidence with execution time and environment.
5. Review and accept an evidence link. Verify the baseline coverage view distinguishes proposed links, accepted evidence, and missing evidence.
6. Generate a frozen report, inspect the preview, and download Markdown and CSV. Edit evidence afterward and confirm the original report remains unchanged.
7. Create a new requirement revision and verify B1 retains the approved original. Demonstrate a reviewer account cannot mutate data if a reviewer has been provisioned.

Separately exercise the PRD's three-requirement baseline acceptance and live extraction/analysis. The one-requirement synthetic replay is deliberately narrow and does not satisfy those gates.

## Automated evidence

Run the [infrastructure acceptance stack](infrastructure-acceptance.md), the full backend suite, frontend lint/types/build, generated-contract drift check, and browser suite. CI contains these jobs; a workflow file alone is not evidence that they ran.

Retain tool versions, source revision/archive checksum, test counts, skip reasons, schema revision, service image versions, duration, and failure logs with credentials/source text removed. Record performance from a representative workload separately; browser duration is not API latency or model quality.

## Backup and restore rehearsal

Backups must cover PostgreSQL **and** private source objects at a consistent application boundary. Freeze writes by stopping web/API, workers, dispatcher, and storage cleanup before taking the pair; leave PostgreSQL and MinIO available for backup reads. Ensure workers have exited and their transactions ended. If a stop kills active work, persisted leases/outbox state must be recovered after restart.

For the local Compose database with default user/database names:

```sh
docker compose stop web api worker dispatcher storage-cleanup
docker compose exec -T postgres pg_dump -U deliverygap -d deliverygap -Fc -f /tmp/deliverygap.dump
docker compose cp postgres:/tmp/deliverygap.dump ./deliverygap.dump
```

Change the user/database arguments if configured differently. The archive stays binary-safe through `docker compose cp`; do not redirect binary dump output through Windows PowerShell. PostgreSQL's custom-format archives are restored with `pg_restore`; dumps do not include cluster roles. See the official [SQL dump guidance](https://www.postgresql.org/docs/16/backup-dump.html) and [pg_dump reference](https://www.postgresql.org/docs/16/app-pgdump.html).

Before restarting writers, export the private bucket with an authenticated S3 backup tool into an encrypted, access-controlled backup location. Preserve exact object keys and bytes, inventory every referenced `document_versions.storage_key`, and compare SHA-256 values with `document_versions.sha256`. Retain bucket access policy and deployment configuration separately from the data archive. Do not make the bucket public for backup.

Restore into a separate empty database and private bucket, never over the running application:

1. Use the same application/schema and service versions. Restore PostgreSQL with `pg_restore --exit-on-error --single-transaction` into the empty destination. Provision required roles/extensions before restore; do not use a `--clean` restore against an existing application database.
2. Restore object keys/bytes and private policy, then verify every referenced source checksum. A database-only restore is incomplete.
3. Start the restored API/worker/dispatcher against the destination services. Keep external AI disabled/unconfigured during rehearsal to prevent accidental provider calls.
4. Verify login, project isolation, original downloads, B1 immutability, frozen report downloads, queued-work recovery, and duplicate-delivery suppression.
5. Record backup timestamps, object/row counts, checksum failures, restore duration, actual recovery point, and actual recovery time. Keep the original environment until the restored copy passes.

The organization must choose a backup schedule, retention period, encryption/access owner, and recovery objectives before real deployment. No backup or restore rehearsal has yet been accepted by adding this runbook.

## Release decision

Do not label the project complete until the plan's outstanding infrastructure, PostgreSQL concurrency, accessibility/security/performance, live-provider, human-reviewed held-out evaluation, and clean-stack/restore gates have recorded results. A provider plan limitation or missing Docker runner is a blocker, not a passed gate.
