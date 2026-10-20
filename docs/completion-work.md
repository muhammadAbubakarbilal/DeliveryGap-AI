# Completion work and acceptance

## Reliability and release preparation — 20 October 2026

- Expanded the real-service harness from two to five cases: missing-object retry exhaustion and explicit recovery, plus killed import/report workers with transaction rollback and duplicate redelivery checks. These cases are implemented but still unexecuted on Linux services.
- Added a locally passing storage-outage regression covering three-attempt exhaustion, no automatic dispatch after failure, idempotent explicit retry, and one parsed output after recovery.
- Fixed Compose forwarding of configured AI Gateway URL/token, embedding model, and session duration to backend services. Provider consent remains enforced; no live provider call was made.
- The complete browser suite exposed an account throttle after repeated successful logins. Scope tests now obtain one in-memory session per role; dedicated login tests still exercise the UI and production throttling is unchanged. The full rerun passed all 13 tests.
- Attempted three real Neon PostgreSQL checks using disposable schemas. All errored during setup because the database has no vector type. The three empty schemas were identified and removed with `DROP SCHEMA ... RESTRICT`; no application tables were changed.
- Prepared a dedicated `deliverygap_test_extensions` namespace for isolated CI databases. Test/worker/smoke search paths include it but exclude `public`; the fixture fails clearly before schema creation if the prerequisite is absent, and now cleans its schema even on later setup failure. Installing the extension in the shared remote database awaits approval; the changed PostgreSQL path remains unverified.
- Added a [release runbook](release-runbook.md) covering full-stack startup, seed replay, a bounded synthetic demonstration, backup/restore procedure, and release evidence.
- Final local checks: **82 backend tests passed, 7 skipped** (two PostgreSQL-only and five infrastructure cases); **13 Chromium tests passed**; frontend typecheck/lint/production build, Ruff/format, strict application mypy, OpenAPI export with unchanged contract, fixture structure validation, and Compose/CI YAML checks passed.

### Completion gates still open

| Gate | Current evidence / next requirement |
| --- | --- |
| PostgreSQL migration, constraints and concurrency | Connection works; vector prerequisite absent. Approve/provision a dedicated test database/namespace, rerun migration and invariant checks, then concurrency cases. |
| Redis/RQ/private-storage recovery | Five runnable cases in dedicated CI; Docker unavailable locally and CI not executed. Provider-worker recovery and S3 service interruption still need coverage. |
| Full-stack startup and backup/restore | Procedure written; actual clean deployment and restoration not rehearsed. |
| AI quality | Gateway configuration exists, but live acceptance is unverified and the prior plan limitation is unresolved. Fifteen proposed development labels are not a human-reviewed held-out benchmark. |
| Release hardening | Broader authorization/security, keyboard/contrast/accessibility, and representative performance measurements remain required. |

The project is not declared complete. These include remaining engineering and acceptance work, not only external provisioning.

## Supervisor demo bootstrap and readiness — 20 October 2026

- Added a PowerShell-ready supervisor walkthrough, technical Q&A, exact isolated Compose startup/reset commands, and a feature readiness matrix. The documentation labels the one-case analysis fixture as deterministic and explicitly not AI inference.
- Added `scripts/seed_supervisor_demo.py`, a local-HTTP-only, authenticated API bootstrap for the synthetic ShopFlow project, parsed scope, exact cited USD-only requirement, approval, and one-item B1. Commands use stable idempotency keys; the script does not directly write database rows or delete data.
- Added tests for the seeder's API sequence, local-URL restriction, and the scope parser's unique source-span assumption.
- Verification: **85 backend tests passed, 7 skipped; all 13 Chromium tests passed;** frontend typecheck/lint/build, fixture structural validation, Ruff/format, strict mypy, script compilation and strict script mypy passed.
- Docker is unavailable in this environment. The seeder was not run against a real API/PostgreSQL/Redis/S3 stack; the full Compose walkthrough, live provider, PostgreSQL acceptance, real worker/storage recovery, and human-reviewed model quality remain open.

## Disposable infrastructure harness — 20 October 2026

- Added a separate Compose acceptance stack and Linux CI job for PostgreSQL, Redis, MinIO, and real RQ source workers. It uses disposable synthetic credentials, no host ports/mounts, unique test schemas/queues, and unconditional CI teardown.
- Added opt-in checks for private immutable originals, a real Redis command outage after DB commit, queue redelivery, killing a worker and its separate RQ child process group, lease recovery, and absence of duplicate source output. A test-only pause and accelerated persisted deadlines make interruption deterministic.
- Local verification: **81 backend tests passed, 4 skipped** (two existing PostgreSQL-only tests and two new infrastructure tests). Ruff lint/format, strict application mypy, editor diagnostics, and YAML parsing/isolation checks passed. No frontend or API contract changes were made.
- Docker remains unavailable locally. The harness is implemented but its real-service execution is **not verified**, and no CI run was triggered in this session. Infrastructure acceptance remains open until a passing run is recorded.
- See [commands, scope, and limitations](infrastructure-acceptance.md). Next: run this harness on a Linux Docker runner, resolve any failures, and extend coverage to storage interruption and operation-worker recovery before clean-stack/backup rehearsal.

## Source dispatcher fairness continuation — 20 October 2026

- Continued Q01 by fixing source-dispatch starvation: active leases, future retry times, and recently dispatched jobs are filtered before the 100-job limit. Eligible uploads can now progress behind a full window of ineligible jobs; expired leases still enter the existing recovery path.
- Added three regression cases, each with 100 preceding ineligible jobs. All failed before the fix and passed afterward, including repeat-dispatch suppression and successful parsing of the eligible original. Existing outage, duplicate-delivery, and expired-attempt recovery tests also pass.
- Verification: full backend suite **81 passed, 2 PostgreSQL-only tests skipped**; focused recovery suite **5 passed** after the final portable fixture-ID adjustment. Ruff lint/format, strict mypy, and editor diagnostics passed.
- This is a bounded reliability fix, not infrastructure acceptance. No CI infrastructure check was added in this continuation. Docker is absent; live PostgreSQL locking, Redis/RQ worker interruption, private S3 recovery, clean-stack startup, and backup/restore remain unverified. Frontend checks were not rerun for this backend-only change.
- Next task: add and run a disposable PostgreSQL/Redis/MinIO acceptance harness in Linux CI, covering persisted outbox recovery and actual worker termination/redelivery without duplicate output.

The implementation plan remains authoritative. The current owner requested the core frontend/backend, including AI pipelines; earlier "AI deferred" notes below are historical checkpoints. Hybrid analysis and extraction are implemented locally with project-scoped provider consent, but live-provider acceptance and evaluation quality gates remain open. See [frontend/backend handoff](frontend-backend-handoff.md).

## Initial implementation baseline, 19 October 2026

Implemented and locally exercised:

- Requirement drafts from a source passage selected in the UI; contributor permissions; exact quote validation; immutable revisions; current-revision approval/rejection; command replay and payload-conflict checks.
- Explicit selection of one approved revision per requirement for a published baseline, pagination, and publication retry after a lost response.
- Database guards for approved requirement content, baseline membership, and append-only review history. The guards and migration round trips have been exercised locally on SQLite, not PostgreSQL.
- Manual artifact creation/revision with retained snapshots and expected revisions; member-proposed evidence links; explicit lead acceptance; stale-review rejection; project-scoped traceability and artifact history.
- Synthetic currency conflict replay, persisted results, and lead review through the UI. Unknown inputs are rejected. This replaces the earlier unsafe arbitrary keyword classifier; it is not the planned AI pipeline. Existing heuristic runs are labeled legacy on migration.
- Generated OpenAPI types used by the new UI; thin requirement, analysis, and evidence routes backed by service functions.

Verification: backend suite 32 passed, 2 PostgreSQL-only tests skipped; Chromium suite 5 passed; Ruff, formatting, mypy, frontend typecheck/lint, production build, and fixture structural validation passed. The browser journey covers a seeded source, draft/review/B1, lost publication response replay, v2 preservation of B1, manual evidence proposal/acceptance, and fixture finding confirmation. It does not prove browser uploads, Redis recovery, S3 operation, multi-requirement extraction, or report downloads. Browser storage is deliberately test-only in-memory storage.

One intermediate browser run timed out while navigating the foundation project screen under concurrent test load. The unchanged full browser suite passed on rerun. This is not a latency benchmark.

## Work still required at the initial baseline

1. Finish Phase 1 acceptance: real PostgreSQL/Redis/MinIO, worker interruption/recovery, original provenance and source immutability enforcement, upload/retry browser paths.
2. Build durable extraction, provider contracts, approved-baseline lexical/dense/hybrid retrieval, pinned embeddings, citation validation, frozen analysis configuration, cancellation/retries, diagnostics and bounded cost. Fixture replay currently supports one exact synthetic currency case only.
3. Finish CSV acceptance on real workers/storage and real bulk worker/storage acceptance. Bounded preview/commit, configurable mapping, import records, artifact history, baseline filters, and transactional bulk link review now exist.
4. Finish reporting acceptance on real workers and performance testing. Frozen Markdown/CSV snapshots, authorized downloads, baseline overview counts, and run/classification/reviewer-state filters now exist.
5. Complete evaluation harness and human-reviewed, family-held-out data; security/accessibility/performance acceptance, clean-stack startup, backup/restore and release documentation.

These are remaining engineering tasks, not all external blockers. The external choices below block live-provider and real-service verification specifically. No phase or release is declared fully accepted by this continuation.

## Sequence

1. Correct requirements: contributor drafts, immutable revisions, evidence checks, idempotent commands, current-version review, one revision per baseline, database protection, and a working review UI.
2. Replace arbitrary keyword analysis with explicitly limited fixture behavior; implement durable extraction/analysis commands with provenance, retry, and review history before live providers.
3. Preserve artifact revisions and append-only link reviews; add validated CSV preview/commit, baseline traceability, and UI.
4. Add frozen report snapshots and downloads, baseline-scoped overview, and connected browser workflow.
5. Verify clean migrations, role/isolation matrix, queue recovery, browser workflow, accessibility, and reproducible setup.

## Actors and invariants

Members create/edit drafts and contribute sources/evidence. Leads approve scope, publish baselines, and finalize reviews. Reviewers only read/download. Archived projects reject mutations. Every command rechecks authorization inside its transaction. Retry keys preserve the original result and reject changed payloads. Review commands reject stale revisions. Published scope, source originals, artifact history, decisions, and report snapshots remain immutable.

## Acceptance

The synthetic browser workflow must upload a source, obtain grounded drafts, approve three requirements, publish B1, review a supported change, record a decision, import and accept evidence, and download a frozen report. A later revision must not alter B1 or an existing report. Negative tests must exercise inaccessible project IDs, reviewer writes, stale decisions, retry replay, malformed input, unavailable dependencies, and recovery without duplicate results.

## External prerequisites

Live inference requires a chosen provider/model, credentials supplied outside chat, and a spending cap. Real PostgreSQL/Redis/MinIO acceptance needs a container runtime or disposable services. Model evaluation requires human-reviewed labels and held-out project families; agent-authored labels are not human-reviewed ground truth.

## Neon setup follow-up

Neon Postgres and managed Auth are now connected and verified through the running application. PostgreSQL is available for real-service verification; Redis and private object storage remain separate prerequisites. Neon AI Gateway deployment and the live provider probe are blocked by the organization's Free plan. See [Neon setup and verification](neon-setup.md) for configuration, evidence, administrator provisioning, and the remaining gateway step. This integration does not complete the pending product phases listed above.

## Latest implementation continuation

- Added immutable-source database guards and explicit artifact revision checks when accepting evidence. Changed/unknown inspected revisions are stale and do not count as accepted current evidence.
- Added bounded task/test CSV preview and durable asynchronous commit, explicit partial acceptance, alias/URL/timezone/duplicate validation, stale-preview rejection, unchanged-row preservation, proposed links, and job history.
- Added immutable report snapshots, escaped Markdown/formula-safe CSV downloads, snapshot preview, baseline coverage filters/counts, and batched evidence snapshot reads.
- Added bounded asynchronous requirement extraction through Neon AI Gateway: frozen input/prompt/configuration, exact-source citation checks, draft-only persistence, fenced network work, cancellation, and authorization rechecks. Its browser test uses a test-only provider; live quality and the paid gateway remain unverified. Large-document chunking was completed in the continuation below; full retrieval/change analysis remains engineering work.
- Connected the new workflows to the requirements and evidence screens; generated OpenAPI types; applied migrations through 0013 to Neon. Fixed a delayed project-list fetch clearing a create-command error.
- Local verification: 45 backend tests passed, 2 PostgreSQL-only tests skipped; 7 Chromium tests passed (45.9 seconds), including imports/report download and extraction into cited drafts. Ruff, formatting, mypy, TypeScript, ESLint, and production build passed. The running app was rebuilt.
- Final Neon PostgreSQL verification: migration upgrade/downgrade/model consistency, extraction idempotency/citation/cancellation, and frozen-report/stale-evidence checks passed: **4 passed in 434.91 seconds**. An earlier run passed five checks but its migration check used an old loaded model while migration 0013 was added; the final rerun passed against the stable schema. No application tables were dropped; tests used disposable schemas.
- Production UI check: signed in to the existing user project, loaded the rebuilt evidence screen, confirmed the CSV/report controls, no horizontal overflow at 390px, and keyboard focus on the preview action.

See [workflow details and limits](imports-and-reports.md). This is substantial progress, not completion of the whole implementation plan. Docker is absent, the real queue/storage stack is not running, AI Gateway is blocked by the Free plan, and human-reviewed evaluation/release acceptance remain open.


## Checkpointed extraction continuation — 19 October 2026

- Added bounded overlapping source windows, up to 32 batches, persistent validated-proposal checkpoints, cross-batch deduplication, and atomic final draft creation. Frozen prompt templates preserve queued-job behavior across deployments. Existing single-batch queued payloads remain supported.
- The requirements UI displays completed batches and the actual limits.
- Fixed operation dispatch starvation: active leases and recently dispatched jobs no longer consume the 25-job eligible dispatch window. Recovery clears stale errors and resumes saved progress.
- New regression tests cover Unicode bounds, overlap, resume/deduplication, no partial drafts after later citation failures, and recovery behind 26 actively leased jobs.
- Docker remains unavailable; real Redis/S3 and live-provider acceptance remain unverified. Full retrieval/change analysis and the release/evaluation gates remain open.
- Verification: 49 backend tests passed (2 PostgreSQL-only skips); 7 Chromium tests passed in 51.4 seconds. Ruff, mypy, TypeScript, ESLint and the production build passed. The rebuilt requirements page was checked in the shared browser. Focused Neon PostgreSQL results are recorded below.
- Corrected manual artifact audit targets to use the internal UUID; valid 120-character external identifiers are preserved in audit details rather than overflowing the PostgreSQL target column. The existing artifact-history test now exercises that maximum length and both audit records.
- Neon PostgreSQL artifact regression: 1 passed in 46.42 seconds, proving maximum-length external IDs, revisions, and UUID audit targets persist correctly in a disposable schema.
- Final Neon extraction run: 6 passed in 374.14 seconds. This covers checkpoint resume/deduplication, atomic failure, Unicode bounds, citation/cancellation/idempotency checks, and recovery without dispatch starvation. Queue delivery is simulated in this regression; this does not replace real Redis/RQ acceptance. Together with the artifact test, 7 focused Neon checks passed.

## Frontend/backend continuation — workflows completed, AI deferred

- Added lead-only split/merge commands. Child drafts require exact source evidence, superseded parent revisions remain untouched in published baselines, future baseline publication rejects superseded requirements, and append-only lineage records every parent/child revision.
- Added atomic/idempotent bulk evidence decisions for up to 100 links with project/role checks and optimistic revisions for both links and artifacts. Any stale or inaccessible item rejects the entire batch.
- Added frozen-report filters by baseline analysis runs, classification, and review state. Run IDs are validated against the project/baseline; the selected filters are stored in each immutable snapshot and rendered in Markdown.
- Connected all three workflows to the requirements/evidence UI and generated OpenAPI/TypeScript contracts. Browser coverage exercises split lineage, bulk acceptance, and filtered report creation.
- AI extraction and analysis work was not changed. Docker-backed Redis/S3 interruption/recovery and backup/restore acceptance remain unavailable in this environment; PostgreSQL-only tests were skipped locally.
- Final verification: **58 backend tests passed, 2 PostgreSQL-only tests skipped; all 9 Chromium tests passed;** Ruff, format check, mypy, TypeScript, ESLint, and the production build passed. The new migration upgraded/downgraded on local SQLite and its lifecycle guard was exercised there; this does not certify PostgreSQL trigger behavior or live Redis/S3 recovery.

## Bounded grounded analysis — 19 October 2026

- Added POST analysis-jobs and a connected change-request form, paged job history, cancellation, polling, and saved findings. Reviewers see the submitted request and cited approved evidence before deciding.
- The selected project/baseline restricts retrieval to approved versions. Frozen input, prompt, candidates, model/retrieval configuration and hashes remain on the durable operation. Current limits: 4000 input characters, 1000 baseline requirements, top five lexical matches, 1200-character content/source excerpts, one provider call per attempt, three recovery attempts, 4000 output tokens and ten findings.
- This is deterministic token-overlap retrieval, not BM25, dense or hybrid retrieval. Excerpts and lexical matching can miss evidence. No retrieved match abstains without a provider call. Invalid input or baseline citations downgrade to insufficient evidence; malformed output fails without findings. All findings remain proposals.
- Provider work runs outside DB locks with a fenced lease. Duplicate delivery cannot duplicate a saved run; cancellation/access checks prevent stale results committing. Existing Redis/RQ dispatch/recovery supports the new job kind without a migration.
- Tests cover exact/invalid citations, idempotent replay/delivery, cross-project and foreign-baseline isolation, no-match abstention, and cancellation. The browser's provider is explicitly synthetic and rejects unknown fixture inputs.
- Still open: real Redis/S3/Linux-worker acceptance, paid gateway/live-model testing, pinned embeddings and dense/hybrid comparison, requests beyond the 4,000-character/10-action limits, calibrated quality evaluation with human-reviewed labels, and remaining release/security/performance gates. No production-ready or model-quality claim is made.
- Verification: full backend suite 53 passed, 2 PostgreSQL-only skips; focused Neon analysis persistence/replay/isolation check passed in 93.94 seconds. Ruff, mypy, TypeScript, ESLint, OpenAPI generation (46 paths), and production build passed. The initial browser suite passed seven tests; the new eighth test timed out on an exact label locator. Browser snapshots confirmed the form was present; the test now follows the project link and selects the dropdown by its accessible role/name.
- Final browser rerun: all 4 scope workflows passed in 47.7 seconds, including queued provider analysis through saved reviewable findings. The other 4 authentication/foundation browser cases passed in the initial full run. The final production build passed and the app was restarted on port 3000.


## Frontend/backend continuation — AI deferred

- Added optional validated CSV header mappings end to end, preserving mappings in the import operation and rejecting missing, reused, unknown, or colliding columns.
- Added downloadable task/test templates and mapping controls; corrected job polling to include running operations.
- Added mapped-import commit regression coverage and a browser upload/parse/original-download check. Existing project access, immutable baselines, evidence review, and frozen reports remain connected.
- No AI implementation changes in this continuation. Real S3/Redis/worker acceptance and the non-AI gaps listed in the handoff remain open.
- Final checks: 54 backend tests passed (2 PostgreSQL-only skips); all 9 Chromium tests passed, including source upload/original download and custom-mapped CSV commit/report download. Ruff, mypy, TypeScript, ESLint, and the production build passed. Rebuilt app restarted on port 3000.

## Structured test execution metadata continuation — AI deferred

- Added nullable `executed_at` and `environment` artifact fields in migration 0015. Manual test artifacts validate timezone-aware input, normalize timestamps to UTC, and retain both fields in revision history and frozen report evidence.
- Added optional CSV environment mapping and safe timestamp parsing before ORM persistence. Identical reimports remain unchanged, while metadata edits create normal artifact revisions.
- Added conditional manual test metadata controls, local-timezone input handling, and metadata display in the artifact and revision history panels; updated the CSV template and import contract documentation.
- Verification: full local backend suite **60 passed, 2 PostgreSQL-only tests skipped**; Chromium suite **9 passed**; Ruff, format check, mypy, TypeScript, ESLint, OpenAPI generation (50 paths), and production build passed.
- Disposable Neon PostgreSQL verification passed for the migration round trip, manual metadata/revision API, CSV metadata commit/reimport, and frozen report metadata (the report snapshot test passed in a separate isolated run after an initial bundled run returned an inconsistent payload). No application tables were dropped.
- Remaining non-AI release gates are live Redis/RQ/S3 recovery and clean-stack/backup rehearsal, plus broader concurrency, authorization, accessibility, performance, and security acceptance. AI/model work remains deferred.

## Hybrid AI and consent continuation

- Added cached 1024-dimensional `qwen3-embedding-0-6b` vectors, bounded gateway embedding batches, BM25 and cosine ranks, reciprocal-rank fusion, top-five candidate diagnostics, and frozen retrieval/model configuration hashes. Completion prompts receive only selected approved baseline evidence; exact request and evidence quotes are validated before persistence.
- Added project-lead-controlled external-AI consent, default-off behavior, audit events, queue-time checks, and worker permission rechecks for extraction and change analysis. Revoked consent prevents new work and stops workers from committing results; already transmitted provider requests cannot be recalled.
- Updated the analysis UI to show candidate ranks and source evidence, incoming request quotes, and warnings that ranks are not confidence and model quality is unmeasured. Browser smoke providers use deterministic synthetic embeddings and never call the live gateway.
- Added an optional evaluation command that records per-case predictions, dataset/config hashes, candidate diagnostics, and citation checks for the synthetic ShopFlow set. It requires an explicit flag before external synthetic data processing and withholds label-agreement metrics until the proposed labels are human-reviewed.
- Added Alembic migrations 0016 (embedding cache and input quotes) and 0017 (default-off provider consent), with SQLite migration round-trip coverage. No live PostgreSQL test URL or container runtime is configured in this environment; Redis/RQ/S3 recovery and clean-stack/backup acceptance remain unverified.
- Live gateway requests and model-quality evaluation were not run. The previous Neon setup notes say the organization's Free plan blocked the provider path. The ShopFlow cases remain development-only and pending human review; no accuracy claim is made.
- Final local verification: **72 backend tests passed, 2 PostgreSQL-only tests skipped; 9 Chromium tests passed;** Ruff/format, mypy, frontend typecheck/lint, OpenAPI generation (51 paths), fixture integrity, and production build passed. The first cold browser-suite run had three transient page-loading failures; each failed flow passed in isolation, followed by a clean full-suite rerun.

## Bounded request decomposition continuation — 20 October 2026

- Added model-guided decomposition into at most 10 source-ordered, non-overlapping spans. Every returned span is validated against the original request using zero-based, half-open Unicode code-point offsets; malformed, overlapping, or invented excerpts fail closed.
- Each atomic request is embedded and retrieved independently against approved baseline requirements. Findings are tagged with request index and exact input offsets; retrieval candidates and sanitized failures are grouped per span for the UI.
- Individual classification failures no longer discard successful sibling findings. The run is marked partial and exposes which spans need retry. Non-actionable notes produce a successful run with no findings and an explicit UI message.
- Added migration 0018 for run outcomes and finding span metadata. Its SQLite round trip preserves existing schema; columns are added directly to avoid SQLite table rebuilds dropping prior unnamed constraints.
- Increased the bounded analysis job timeout/lease to 1500/1560 seconds to cover the maximum 11 completion calls plus up to 1010 embedding inputs in 64-item batches. Consent, cancellation, authorization and fencing checks remain in the worker path.
- Updated the analysis UI, generated API contract, frozen report evidence, and handoff documentation. Local fake providers validate request splitting, partial results, no-actionable behavior, citations, and cancellation; these are not live provider or quality results.
- Verification: **76 backend tests passed, 2 PostgreSQL-only tests skipped; all 11 Chromium tests passed.** Ruff, format check, strict mypy, frontend typecheck/lint, OpenAPI export (51 paths), TypeScript generation, and production build passed.
- Migration 0018 passed the disposable SQLite upgrade/downgrade/schema-drift round trip. PostgreSQL migration behavior, Redis/RQ worker interruption, live provider calls, and model quality remain unverified; the two PostgreSQL-only tests were skipped because `TEST_DATABASE_URL` is unavailable.

## Explicit provider-operation retries — 20 October 2026

- Added a project-authorized, idempotent retry command for failed extraction and change-analysis operations. It rejects unsupported job types, non-failed operations, exhausted three-attempt budgets, reviewers, inaccessible projects, and projects without current external-AI consent.
- Analysis retries preserve the frozen input and start a fresh attempt without carrying a failed result forward. Extraction retries preserve validated batch checkpoints so completed batches are not reprocessed; duplicate delivery after success remains a no-op.
- Added retry controls to both job histories, gated by contributor access, consent and remaining attempts. The UI reuses its idempotency key across ambiguous network failures, refreshes status after acceptance, and explains retry exhaustion.
- Regression coverage exercises analysis-provider recovery, replay after completion, worker duplicate delivery, retry denial for reviewers/outsiders/revoked consent/wrong state/exhausted attempts, and extraction recovery from a later-batch failure without duplicate drafts. Chromium verifies the retry control and repeated request key after a simulated lost response.
- Verification: **78 backend tests passed, 2 PostgreSQL-only tests skipped; all 12 Chromium tests passed.** Ruff, formatting, strict mypy, frontend typecheck/lint, OpenAPI export (52 paths), generated API types, evaluation-fixture structural validation, and production build passed. The browser API uses the disposable synthetic executor.
- Live Redis/RQ recovery, PostgreSQL-specific migration/concurrency behavior, private object storage, live provider behavior, human-reviewed evaluation, and release/backup gates remain open. Retry does not substitute for those end-to-end acceptance checks.
