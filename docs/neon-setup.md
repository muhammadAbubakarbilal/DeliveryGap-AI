# Neon setup and verification

## Status (2026-10-19)

The app uses the production branch of project `holy-darkness-26600071` in organization `org-withered-credit-60821371`. Neon Postgres and existing Neon Auth were verified with the running app. Full `neon deploy` is blocked: this organization's Free plan does not support AI Gateway. A real gateway request returned HTTP 403. Keep `aiGateway: true` in [neon.ts](../neon.ts), upgrade the organization, then rerun deployment and the gateway probe below.

Neon supplies managed services; the Next.js frontend and FastAPI server currently run locally. Redis, private object storage, workers, and the remaining product workflows are separate from this setup; see [remaining implementation work](completion-work.md).

## Configuration and runtime

The CLI is installed globally (`neon` 8.8.0). PowerShell requires quoting the comma-separated services argument:

```powershell
neon init -y --no-agent-setup --org-id org-withered-credit-60821371 --project-id holy-darkness-26600071 --branch production --services 'postgres,auth,ai-gateway'
neon deploy
```

The initial automatic agent setup installed Neon skills but failed on the optional GitHub Copilot plugin. Initialization succeeded with `--no-agent-setup`. Browser authentication succeeded. Because full deployment was blocked, service variables were pulled explicitly:

```powershell
neon env pull --service postgres --service auth
neon env pull --service ai-gateway
```

Credentials are in ignored `.env.local`. Both runtimes load the root environment. Never commit this file. A random `NEON_AUTH_COOKIE_SECRET` was generated locally for the SDK. [Environment examples](../.env.example) list variable names without credentials. For HTTPS hosting, set `APP_ORIGIN`, `COOKIE_SECURE=true`, and the private `INTERNAL_API_URL` appropriately.

FastAPI retains SQLAlchemy and psycopg. `DATABASE_URL` is used for application traffic; `DATABASE_URL_UNPOOLED` is preferred by Alembic. Standard Neon PostgreSQL URL schemes are normalized without dropping TLS query options. Migration 0010 adds a unique managed-identity binding.

Next.js proxies Neon Auth through `/api/auth/[...path]`. The login screen supports managed sign-in. FastAPI validates JWT signatures with Neon JWKS, issuer, audience, expiry and subject, then issues a bounded application session. Managed identities must be explicitly linked to application users; Neon roles and email claims do not grant project access or administrative rights. Sign-out revokes the application session and signs out of managed auth.

Provision the permanent account in Neon Auth, then explicitly link its user ID:

```powershell
& '.venv/Scripts/python.exe' scripts/link_neon_user.py --subject '<Neon Auth user ID>' --admin
```

The script verifies the identity against the selected branch before linking. The permanent administrator has since been provisioned and sign-in verified. Live verification used a temporary synthetic account; its random credentials are held only in ignored `.cache/neon-smoke.json`.

The worker-side [gateway adapter](../apps/api/app/ai_gateway.py) reads Neon gateway variables, bounds input/output, and sanitizes errors. Bounded extraction and hybrid change analysis now use the adapter when dispatched. A project lead must explicitly enable external AI processing first; consent defaults off and revocation is rechecked by workers. The earlier real provider probe returned HTTP 403 because this organization is on the Free plan, so live inference remains unverified. Migrations 0016/0017 must be applied to PostgreSQL before deploying these changes.

## Run and verify

```powershell
& '.venv/Scripts/python.exe' -m alembic upgrade head
npm run build
# Separate terminals, or the API: dev and Web: production editor tasks:
uv run uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000 --reload
pnpm --filter @deliverygap/web start
node apps/web/scripts/neon-smoke.mjs
& '.venv/Scripts/python.exe' scripts/test_neon_gateway.py
```

The browser smoke requires the synthetic account created by `scripts/neon_auth_smoke_setup.py` and linked with the operator script. It creates and archives a test project. It tests real services; it is distinct from the isolated Playwright regression suite.

Observed production build and real-service browser output:

```text
npm run build: exit 0
Next.js 16.4.2 (Turbopack)
Compiled successfully in 18.4s
Generating static pages using 7 workers (6/6)
PASS Neon Auth: browser sign-in and protected application access
PASS Neon Auth: session restoration after reload
PASS Neon Postgres: project written through UI/API and read after reload
PASS Neon Auth: managed sign-out and protected-page/API denial
```

Backend regression: 36 passed, 2 skipped (PostgreSQL-only cases skipped in the local SQLite run). Direct Neon PostgreSQL migration and managed-auth checks: 3 passed in 200.29s, using a disposable schema. The existing isolated Chromium regression suite passed all 5 tests in 52.7s. Ruff, mypy, frontend typecheck and lint passed. The editor reported no errors in either application.

The real Neon PostgreSQL idempotency suite also passed: `12 passed, 1 warning in 438.58s`. This includes concurrent identical requests and concurrent conflicting payloads, rollback recovery, actor scoping, and authorization rechecks. The warning is Starlette's test-client HTTPX deprecation; no PostgreSQL cases were skipped in this run.

Blocked commands:

```text
neon deploy: exit 1
This neon.ts enables the AI Gateway, which isn't available on the Free plan
scripts/test_neon_gateway.py: exit 1
AI Gateway returned HTTP 403; check plan, credits and configuration
```

Upgrade at the [organization billing page](https://console.neon.tech/app/org-withered-credit-60821371/billing), rerun `neon deploy`, and rerun the gateway probe before considering all three services verified. No paid-plan change was made by the agent. Next.js also warns that `next start` is not its recommended standalone-output entrypoint; local startup and the real-service browser checks nevertheless passed. Hosting should package and start the generated standalone server.
