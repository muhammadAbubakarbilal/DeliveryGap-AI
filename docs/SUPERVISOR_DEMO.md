# DeliveryGap AI — supervisor demonstration

## What the demonstration shows

DeliveryGap AI keeps approved scope connected to later change requests, reviewer
decisions, and delivery evidence. Findings are proposals, not decisions; missing
evidence is not proof that work was not implemented.

The existing application includes authenticated projects and roles, private
document handling, cited requirement revisions, immutable baselines, persisted
change-analysis operations, human finding decisions, delivery evidence,
traceability, dashboard data, and frozen reports. See
[demo readiness](./DEMO_READINESS.md) for what has and has not been verified.

## Start locally on Windows without Docker

The local demonstration deliberately uses a separate SQLite database and
filesystem object storage. It does not connect to the configured Neon database
for application data, and Redis is not required. The local worker invokes the
existing parsing, extraction, analysis, import, and report handlers; it does
not mark jobs successful without running their handlers.

Prerequisites: the repository's `.venv`, installed Python dependencies, Node.js,
and installed pnpm workspace dependencies. From the repository root:

```powershell
uv sync --frozen
pnpm.cmd install --frozen-lockfile
.\scripts\start-local.ps1
```

The startup script runs Alembic against `.cache\deliverygap-demo.db`, prompts
for a local administrator password (12+ characters), then starts the API,
polling worker, and Next.js development server. The password is neither written
to the repository nor printed by the script. Open
[http://localhost:3000](http://localhost:3000) and sign in using the administrator
email `admin@deliverygap.example.com` and the password you entered.

Service logs and the PID manifest are kept under the ignored `.cache`
directory. Stop only these started processes with:

```powershell
.\scripts\stop-local.ps1
```

The local database and source objects remain between starts. The administrator
seed is idempotent and does not change an existing account's credentials.
`-SkipAdminSeed` is intended only when a local administrator already exists.

## ShopFlow walkthrough

The synthetic source is
[`datasets/synthetic_project/scope.md`](../datasets/synthetic_project/scope.md).
After starting the app, run the API-based bootstrap from another PowerShell
terminal:

```powershell
$env:DELIVERYGAP_API_URL = "http://localhost:8000"
$env:APP_ORIGIN = "http://localhost:3000"
& '.venv\Scripts\python.exe' scripts\seed_supervisor_demo.py
```

The script prompts for the local administrator password and uses authenticated
application API calls to create the ShopFlow project, parse its source, create
and approve the cited REQ-003 USD-only requirement, and publish the one-item
immutable baseline B1. It is idempotent and non-destructive. It does **not**
seed findings, decisions, evidence, or reports, and it does not enable external
AI consent.

Walk through the persisted records in the UI:

1. Open ShopFlow and inspect the source passage and original download.
2. Inspect REQ-003, its exact cited source, and published B1.
3. Submit a change request against B1 and inspect the persisted operation and
   findings if provider configuration and explicit project consent permit it.
4. Review a finding and record a human decision with a note.
5. Add or import delivery/test evidence, review its requirement link, and
   inspect traceability gaps.
6. Generate a report, then preview and download the frozen snapshot.

The application also has a clearly labeled deterministic currency-analysis
fixture used in automated tests. It recognizes only the exact EUR/GBP request
against this one-item USD-only baseline; it is not model inference or a general
fallback classifier. Do not present fixture output as a live AI result.

## AI and database boundaries

Live extraction and analysis require valid Neon AI Gateway configuration and a
project lead's explicit external-AI consent. Consent is off by default. Never
enable it merely to make a test pass. Use synthetic ShopFlow text only for
provider requests. The live catalog response previously succeeded, but a
catalog check is not a model inference; current live inference and the five
requested scenario outcomes remain unverified until performed and recorded in
[demo readiness](./DEMO_READINESS.md).

SQLite supports local workflow demonstration and tests, but it is not the
planned PostgreSQL/pgvector acceptance target. PostgreSQL-specific migrations,
vector operator behavior, concurrency, and live database integration must be
verified separately before claiming those properties.

## Technical talking points

- Lexical and embedding retrieval are fused with reciprocal-rank fusion;
  retrieval ranks are not confidence probabilities.
- Source citations are checked against persisted project/baseline evidence.
- Baselines pin approved requirement versions and are not rewritten by later
  edits.
- Provider findings are proposals. An authorized human records the decision.
- Jobs are persisted in the database. The local worker runs the same bounded
  handlers without Redis/RQ, while PostgreSQL/Redis recovery remains a
  separate infrastructure verification.
- Reports are frozen snapshots of persisted project data.
