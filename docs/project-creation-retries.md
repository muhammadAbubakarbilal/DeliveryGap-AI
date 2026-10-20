# Project creation retries

`POST /api/v1/projects` requires an authenticated workspace administrator, valid Origin/CSRF headers, and an `Idempotency-Key`. Keys contain 1–128 ASCII letters, digits, periods, underscores, colons, or hyphens. Missing or malformed keys return 422 without creating a project.

The key is scoped to the actor and the project-creation operation. There is no existing project scope before creation. The database stores the validated request hash, resulting project ID, and original response in `project_creation_requests` (migration `0002`). Keys do not expire automatically.

- Same actor, key, and validated fields: return the original 201 response, even if the project has since been edited.
- Same actor and key with different validated fields: return 409. Whitespace normalization and default fields follow the Pydantic request schema before hashing.
- A different key intentionally creates a separate project, including when the fields are identical.
- A different administrator has an independent key namespace.
- Authentication, CSRF, and current administrator privileges are required on every replay.

The project, creator's lead membership, creation audit, and retry record commit together. A failed transaction consumes no key. Concurrent requests compete on the actor/key primary key; the losing transaction rolls back its project, membership, and audit before reading the winning result. Only this operation owns the transaction in the project-creation service.

The web form retains a key for each submitted payload while the page is mounted and a creation attempt remains unresolved. Resubmitting unchanged fields after a network error reuses the key. A successful response clears the attempt; a subsequent intentional creation gets a fresh key. Keys are held in memory, not browser persistence: reloading or leaving the page loses unresolved keys. After that, check the project list before starting another creation. API clients that need recovery across restarts must retain and reuse their key.

Migration `0002` must be applied before serving the updated API. Downgrading to `0001` preserves projects but removes retry records and therefore removes replay guarantees for old keys. The new API requires migration `0002`; do not run it against the downgraded schema.

## Verification

The backend tests cover exact replay, request conflicts, distinct keys/actors, normalized fields, replay after edits, header validation, revoked privileges, CSRF/session checks, and transaction rollback. The migration test upgrades from foundation with an existing project, checks metadata drift, downgrades/re-upgrades, and cleans the disposable schema. The browser test commits a creation then drops its response, retries through the form, and checks that only one project exists; it also verifies fresh keys for intentional subsequent creation.

Two concurrency cases require a disposable PostgreSQL database via `TEST_DATABASE_URL`. They synchronize competing inserts and assert one project, membership, retry record, and creation audit for identical and conflicting payloads. They skip explicitly when using SQLite. The existing CI PostgreSQL service runs these cases; no remote CI result is claimed here.
