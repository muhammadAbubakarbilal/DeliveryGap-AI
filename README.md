# DeliveryGap AI

An internal workspace for approved requirements, change proposals, human decisions, and delivery evidence. The project is under development; [completion status](docs/completion-work.md) records the remaining work. Findings are proposals, and missing evidence is not proof of missing implementation.

## Local Docker-free demo

The Windows demo runs Next.js, FastAPI, a database-polling worker, SQLite, and
private filesystem storage without Docker, Redis, or writes to the configured
Neon database. It requires the existing Python virtual environment, Node.js,
and installed pnpm dependencies:

```powershell
uv sync --frozen
pnpm.cmd install --frozen-lockfile
.\scripts\start-local.ps1
```

Stop with `.\scripts\stop-local.ps1`. The startup script prompts for the local
administrator password. For the authenticated ShopFlow bootstrap and the
precise scope of local verification, see [the supervisor demo](docs/SUPERVISOR_DEMO.md)
and [demo readiness](docs/DEMO_READINESS.md). SQLite is a local demonstration
fallback, not PostgreSQL/pgvector integration acceptance.

See [imports, extraction, and reports](docs/imports-and-reports.md) for workflow limits, queue behavior, and verification boundaries. The Neon AI Gateway currently requires an organization plan upgrade before model calls can work.
For the synthetic supervisor walkthrough, local startup commands, and verified versus unverified gates, see [the supervisor demo](docs/SUPERVISOR_DEMO.md) and [demo readiness](docs/DEMO_READINESS.md).
ShopFlow bootstrap uses the authenticated local API:
`& '.venv\Scripts\python.exe' scripts\seed_supervisor_demo.py`.

## Checks

```powershell
uv run pytest -q
uv run ruff check apps/api scripts
uv run mypy
pnpm typecheck
pnpm lint
pnpm build
pnpm --filter @deliverygap/web exec playwright test
```

Browser fixtures use a disposable database, test-only storage/executor, and synthetic data. Real PostgreSQL checks can be run with `scripts/test_neon_postgres.py`; it creates disposable test schemas and never drops application tables. Real Redis/S3 recovery and production release acceptance remain separate gates.

## Functional submission

The local functional workflow is ready for demonstration: sign in, create a project, upload or author sources, review and publish requirements, analyze a change request, review findings, import evidence, inspect traceability, and download a frozen report. Run the checks above for the verified submission path.

## Optional infrastructure reference

Use the [release runbook](docs/release-runbook.md) for full-stack startup, seed replay, the synthetic demonstration, and backup/restore rehearsal. The [isolated infrastructure harness](docs/infrastructure-acceptance.md) exercises real queue/storage failure paths when a Linux Docker runner is available.
