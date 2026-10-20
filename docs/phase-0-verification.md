# Phase 0 verification ledger

Current status and corrections: see [completion work](completion-work.md). Earlier entries are historical and overstate some original behavior: the analysis implementation used arbitrary keyword heuristics, baseline UI omitted the required retry key, and evidence writes lacked revision history and member permissions. The latest implementation repairs those paths; full phase acceptance remains open. Current local verification is 32 backend passes with 2 PostgreSQL-only skips and 5 Chromium passes, plus static checks and a production build.

## Skills (17 October 2026)

- Sixteen canonical skill files remain in the engineering plugin.
- Sixteen `.agents/skills` entrypoints passed the bundled validator.
- Codex CLI 0.162.1 app-server `skills/list` returned all sixteen enabled with `repo` scope and no errors. The verifier exited 0.
- Frontend, backend/database, and QA canonical instructions were applied in three read-only delegated invocations in the previous session. This is separate evidence from runtime discovery.
- No global skill catalog or Codex configuration was modified.
- Previous claims that project discovery and plugin CLI commands were unsupported were incorrect; see [skill discovery](engineering-skills.md).

## Previous completed test runs

- Backend API behavior: 8 tests passed using SQLite, not PostgreSQL.
- Ruff and mypy passed.
- Frontend TypeScript and ESLint passed; production build exited successfully after the session-expiry redirect change.
- OpenAPI export was unchanged.

## Infrastructure investigation

Elevated read-only checks found no installed Docker package, Docker/PostgreSQL services, or WSL distribution. `winget show --id Docker.DockerDesktop --exact --source winget --accept-source-agreements` succeeds and lists an installer. The previous winget access failure was a sandbox limitation, not proof that installation is impossible.

Docker installation and host virtualization setup have not been performed. A provisioned Docker runtime or a dedicated disposable PostgreSQL database supplied through `TEST_DATABASE_URL` is needed for real database verification. Existing fixtures isolate tests in unique schemas; they must not be pointed at production credentials. SQLite results cannot prove PostgreSQL locking or migrations.

## Follow-up verification (19 October 2026)

- Fixed the account row being hidden below 560px; mobile sign-out has a 44px minimum target and retains visible keyboard focus.
- Extended the browser smoke suite to sign out by keyboard at 390px and confirm protected navigation returns to login. Scoped membership assertions to the table to avoid matching the sidebar account name.
- Frontend typecheck, ESLint, and production build passed. Both Playwright foundation tests passed on the final run (37 seconds).
- The first browser run failed on navigation timing and an ambiguous name assertion; the final run followed the completed production build and corrected assertion.
- These browser checks use the disposable smoke API; they do not establish PostgreSQL constraints, concurrency, or clean-stack acceptance.
- Corrected the implementation plan's stale pre-implementation status. Phase 1 remains unstarted.

## Remaining foundation work

- Execute PostgreSQL migration upgrade/downgrade/schema-drift and integration checks.
- Verify concurrency and the complete role matrix; current tests do not establish either exhaustively.
- Execute the two project-creation concurrency tests against PostgreSQL; retry behavior is implemented and locally verified with SQLite and browser tests (see below).
- Finish the Phase 0 documentation, human review of the proposed synthetic evaluation labels, and clean-stack acceptance gate before declaring foundation complete.

Phase 1 has not begun. Its first implementation task remains D01: private storage and bounded upload validation with source schema, followed by D02 durable jobs/outbox before long-running parsing.

## Project creation retries (19 October 2026)

- Added required `Idempotency-Key`, actor-scoped durable results, validated payload hashes, original-response replay, and 409 for changed fields. Project, lead membership, audit, and retry record share one transaction.
- Added reversible migration `0002`; the web form retains keys for retrying unresolved submissions and generates new keys after success. See the [contract and recovery limits](project-creation-retries.md).
- Confirmed the original bug with a failing regression test: identical requests created different project IDs.
- Backend: 19 passed, 2 skipped. The skipped cases require PostgreSQL for concurrent identical/conflicting requests. `TEST_DATABASE_URL` was not configured.
- Migration upgrade, metadata drift, downgrade/re-upgrade, and preservation of existing project data passed on the disposable SQLite test database. These are not PostgreSQL verification results.
- Browser: all 3 tests passed (28.7 seconds), including lost-response retry, deliberate new creation, existing project administration, reviewer restrictions, and mobile keyboard sign-out.
- Ruff lint/format and mypy passed. OpenAPI and frontend types were regenerated for the required header.
- Frontend TypeScript, ESLint, and production build passed after the idempotency change.

## Initial synthetic evaluation fixtures (19 October 2026)

- Added the PRD's five ShopFlow baseline requirements and meeting note as fictional Markdown sources.
- Added 15 development cases spanning all five classification labels, exact evidence references, and rationales. All labels are agent-authored proposals pending human review; the hand-labeling gate remains open.
- Added `pnpm fixtures:validate` and its CI step. Direct execution of the validator passed for all 15 cases and five source anchors; editor diagnostics found no errors in the script, JSON fixture, or package manifest.
- The validation checks structure and source integrity only. No classifier, provider, parsing pipeline, retrieval benchmark, or model-quality evaluation was run.
- See the [review rubric and split policy](evaluation.md). The entire ShopFlow family is development-only; no held-out evaluation is claimed.
- This continuation changes fixtures, documentation, and their CI check. Previous application test results above were not rerun and are not new evidence. PostgreSQL/concurrency and clean-stack acceptance remain unverified; Phase 1 remains unstarted.

## Phase 1 source slice verification (19 October 2026)

- Added focused source API tests covering supported Markdown upload, immutable idempotent replay, canonical line spans, original download, manual authored text, oversize and malformed input rejection, and project membership isolation.
- The focused source suite passed: 4 tests.
- The full backend suite passed: 23 tests, with 2 PostgreSQL-only concurrency tests skipped because `TEST_DATABASE_URL` is not configured.
- Ruff and mypy passed after adding the tests. The source implementation uses the existing private-storage adapter, transactional source/job/outbox records, and fenced parser worker.
- These checks use the disposable SQLite test path for local execution. They do not prove PostgreSQL foreign keys/locking, Redis recovery, object-storage behavior, or a clean Compose stack.
- The source slice still requires real PostgreSQL/Redis/MinIO acceptance and browser coverage before the Phase 1 gate is complete.

## Phase 2 approved-scope slice (19 October 2026)

- Added versioned requirement records with project-composite provenance to persisted source versions/spans.
- Added append-only approve/reject review events with optimistic expected-version checks; ungrounded requirements cannot be approved.
- Added transactional baseline publication with approved-only membership, project-scoped composite references, immutable numbered items, and baseline listing.
- Added migration `0004` and API regression coverage for grounded approval, baseline publication, and ungrounded rejection.
- Requirement/baseline tests passed: 2. Full suite passed: 25 tests, with 2 PostgreSQL-only skips before this documentation update.
- A schema test exposed and fixed the missing `(project_id, source_span_id)` uniqueness needed for safe cross-project source provenance.
- Added the reviewer UI at `/projects/{id}/requirements`, linked from project detail, with loading/error/empty states, grounded approval actions, baseline publication, and published-baseline listing.
- Regenerated [OpenAPI types](openapi.json) and the frontend typecheck, lint, and production build passed. The new route is included in the build route manifest.

## Phase 3 deterministic analysis slice (19 October 2026)

- Added baseline-scoped analysis runs and findings with the five PRD classification labels.
- Added deterministic fixture-safe classification for conflict, potential addition, ambiguity, in-scope matches, and insufficient evidence.
- Added append-only finding decisions with expected-status concurrency checks.
- Added migration `0005`, OpenAPI regeneration, and an end-to-end test from source upload through baseline publication, analysis, and human confirmation.
- Full backend suite passed: 26 tests, with 2 PostgreSQL-only skips. Ruff and mypy passed.
- This is workflow validation only. It is not a hosted-model evaluation, does not claim model quality, and still needs the full asynchronous provider/retrieval pipeline described by the plan.

## Phase 4 evidence-link slice (19 October 2026)

- Added project-scoped manual delivery artifacts for tasks, tests, and pull requests with safe URL validation and deterministic manual upsert identity.
- Added proposed/accepted/rejected requirement-to-artifact links and baseline-scoped traceability queries.
- Lead/admin-created links are accepted immediately; member-created links remain proposed until review. Review actions are audited and project-authorized.
- Added migration `0006`, regenerated OpenAPI types, and passed Ruff/mypy plus the migration round-trip check.
- CSV preview/commit, artifact revision history, traceability UI, report snapshots, and full PostgreSQL verification remain next.
