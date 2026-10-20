# Demo readiness

Status: **Docker-free startup and local services are implemented; a complete
end-to-end demonstration is not yet certified.** This document separates
implemented behavior from test evidence and real-service verification. A
passing unit or browser test is not proof of a complete user workflow.

| Area | Implemented | Tested | Verified against real local services | Fixture-only / blocked |
|---|---|---|---|---|
| Native Windows startup/shutdown | PowerShell scripts launch API, local database-polling worker, and Next.js; shutdown uses recorded process IDs | Script syntax and worker tests | Pending full startup and workflow run | PostgreSQL/Redis not used by this local mode |
| Local persistence and uploads | SQLite migrations and private filesystem storage, immutable writes, bounded reads | Storage unit tests and SQLite migration tests | Pending startup/upload/download run | Not PostgreSQL/pgvector acceptance |
| Authentication and project roles | FastAPI sessions, project membership and authorization | API and browser regression suites | Pending fresh local login run | Fresh local administrator required |
| Document sources | PDF/DOCX/TXT/MD parsing and explicit processing errors | Parser and upload/download regression tests | Pending local upload and parsed-source inspection | External S3 recovery not part of local mode |
| Requirements and baselines | Cited drafts, review, revisions, immutable published baselines | API and browser tests | ShopFlow bootstrap is API-based; fresh local execution pending | Current bootstrap creates only REQ-003 and one-item B1 |
| Extraction and change analysis | Persisted operations, hybrid BM25/vector candidate ranking, provider validation, citation checks | Synthetic provider and pipeline tests | Live local provider inference pending | Consent defaults off; provider plan/credentials may block |
| Findings and decisions | Persisted proposals, supporting citations and reviewer history | API and browser tests | Pending local full-workflow run | Deterministic currency case is a narrow fixture only |
| Delivery evidence and traceability | Manual/imported evidence, links, review, gaps | API and browser tests | Pending local full-workflow run | No synthetic evidence dataset is seeded yet |
| Dashboard and reports | Project metrics and persisted frozen report snapshots | API and browser tests | Pending local full-workflow run | Report results must be checked after worker completion |
| Five live ShopFlow AI scenarios | Provider pipeline can process consented requests | Pipeline tests use controlled synthetic providers | Not verified | New scope, existing scope, conflict, ambiguity, and insufficient-evidence live outcomes not run |
| PostgreSQL/pgvector | Production data layer and migrations are implemented | PostgreSQL-specific integration checks exist | Not verified in this local SQLite startup | Do not claim SQLite verifies pgvector or PostgreSQL concurrency |
| Complete seeded/resettable demo | API seeder creates project, source, cited requirement, and B1 idempotently | Seeder unit tests | Pending local invocation | Findings/evidence/report seeding and project-scoped reset are incomplete |

## Start and stop

From the repository root in PowerShell:

```powershell
uv sync --frozen
pnpm.cmd install --frozen-lockfile
.\scripts\start-local.ps1
```

The startup script forces an isolated local SQLite URL and filesystem storage,
runs migrations, creates a local administrator after prompting for a password,
then starts API (`8000`), worker, and web (`3000`). It never uses the
`.env.local` database URL for application data. Existing AI Gateway settings
may still be read by the API; provider calls require explicit project consent.

Open `http://localhost:3000`. Seed ShopFlow through the authenticated API:

```powershell
$env:DELIVERYGAP_API_URL = "http://localhost:8000"
$env:APP_ORIGIN = "http://localhost:3000"
& '.venv\Scripts\python.exe' scripts\seed_supervisor_demo.py
```

Stop the local processes while preserving the local database and uploaded
objects:

```powershell
.\scripts\stop-local.ps1
```

Logs and process metadata are stored in the ignored `.cache` directory. Do not
delete that directory to reset an application that may contain other local
work; a project-scoped reset utility is not yet implemented.

## Verification record

Latest focused local-worker verification:

- Filesystem and recovery tests: **20 passed, 1 skipped**. The skipped test
  needs a Windows directory-symlink privilege unavailable to this account.
- PowerShell parser: startup and shutdown scripts parsed successfully.
- Real startup, fresh login, upload-to-report browser workflow, live provider
  inference, PostgreSQL/pgvector integration, and five AI scenarios: **not yet
  verified**.

Re-run relevant suites before the demonstration:

```powershell
& '.venv\Scripts\python.exe' -m pytest -q
& '.venv\Scripts\python.exe' -m ruff check apps\api scripts
& '.venv\Scripts\python.exe' -m mypy
pnpm.cmd typecheck
pnpm.cmd lint
pnpm.cmd build
pnpm.cmd --filter @deliverygap/web exec playwright test
pnpm.cmd fixtures:validate
```

The deterministic currency fixture and synthetic-provider tests are useful for
regression checks only. They do not establish live model quality or make
predictions for arbitrary requests.

## Remaining gaps

1. Run the new scripts, log in, seed ShopFlow, and execute document-to-report
   end-to-end against the local API, SQLite, filesystem storage, and worker.
2. Verify an actual provider request only after checking configured credentials
   and explicit ShopFlow consent; test the five requested scenarios without
   fabricating outputs.
3. Expand the ShopFlow dataset and seed evidence/findings/report state through
   application APIs; provide a reset scoped to only that synthetic project.
4. Run PostgreSQL/pgvector integration separately. SQLite is not a substitute.
5. Record the exact outcome of a real-browser workflow and all unavailable
   provider or database dependencies before claiming demonstration readiness.
