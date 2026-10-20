# Imports, extraction, and reports

## Where to find them

In a project, **Delivery evidence and traceability** includes the CSV preview, explicit commit, background job history, baseline coverage filters, transactional bulk evidence review, and filtered frozen-report generation, preview, and Markdown/CSV downloads. **Review requirements and baselines** includes source-based extraction and its job history/cancellation, plus source-grounded split/merge drafts with lineage. Manual drafts remain available.

These workflows require the dispatcher and worker. Queued work persists in PostgreSQL if Redis or workers are unavailable. This Windows host currently has no Docker installation, so the local production worker/storage stack has not been started. Browser tests use an explicitly isolated test executor and in-memory storage; they do not prove Redis or S3 behavior.

## CSV contract

UTF-8 (optional BOM), maximum 1 MB and 500 rows. Task headers: `external_id,title,description,status`; test headers: `test_id,name,result,executed_at`. Optional columns: `environment,url,requirement_id,related_requirement_id,updated_at` (the environment field applies to tests). Both requirement aliases are supported, but contradictory values fail row validation. Requirement codes resolve only against the selected published baseline. Timestamps must include a timezone and are normalized to UTC; URL values must be HTTP(S).

Task states: `todo`, `open`, `in_progress`, `done`, `closed`, `blocked`, `cancelled`. Test states: `pass`, `fail`, `skipped`, `blocked`, `not_run`. Case and surrounding whitespace are normalized; `passed`/`failed` and `in-progress` aliases are recognized. Duplicate identifiers invalidate every occurrence. Unknown headers fail explicitly rather than silently discarding columns.

Preview stores normalized rows, row errors, the source SHA-256, selected baseline, and observed artifact revisions. No artifacts are written until confirmation. Partial import requires an explicit checkbox. A worker commits valid rows atomically; a stale preview fails rather than overwriting newer evidence. Identical reimports do not create revisions. Test artifacts retain execution time and environment as structured metadata, in addition to the imported CSV snapshot. CSV references only create proposed links. CSV artifact revisions are made through another preview/import; manual artifact revisions use the manual editor.

Accepted links record the artifact revision inspected. Acceptance commands check both link and artifact revisions. If an artifact changes, the link remains historical acceptance of the old revision and is displayed as stale. Unknown inspected revisions from older data are also stale. Baseline coverage counts only accepted, current links; absence is not proof of missing implementation.

## Reports

A report job freezes the selected baseline, exact source excerpts, requirement revisions, finding proposals and decision states, inspected artifact snapshots, link states, and timestamp under the project write lock. The report snapshot has database update/delete guards. Downloads render only that saved payload, so later reviews or artifact revisions do not rewrite an existing report. Create another report for newer state. CSV formula prefixes are neutralized and Markdown user content is escaped.

Reports can filter findings by selected analysis runs, classification, and reviewer state. Empty filters include all matching values, and a selected run must belong to the chosen project and baseline. The snapshot records the filter values and resulting findings. Repeated runs remain separate and are not counted as distinct approved changes. Current bounds are 1000 requirements, 10000 links, and 10000 findings per snapshot.

Leads can bulk accept/reject up to 100 traceability links in one command. The command checks every link and artifact revision before writing any decisions, saves append-only decision history, and supports idempotent retry; a stale item rejects the whole batch.

Requirement split/merge is lead-only. Each child is a source-grounded draft; the operation records immutable parent/child revision edges and marks parent requirements superseded for future baselines. Previously published baselines remain unchanged. New baselines cannot include superseded requirements.

## Extraction

For each batch, the worker sends one bounded request to Neon AI Gateway (`gpt-5-mini`, maximum 4000 output tokens), outside database locks. The command freezes source text/spans, source hash, prompt, model configuration, and configuration hash. Sources are divided into at most 32 batches of 16000 serialized characters. Passages use 1000-character windows with 200-character overlap, including Unicode-safe serialized-size bounds. Each delivery processes one batch, with at most 20 proposals. Validated proposals are checkpointed; all drafts are committed atomically after the final batch. Duplicate span/content proposals across batches are removed. Interrupted batches have three attempts; completed batches are not repeated. Empty or oversized sources return an explicit validation error. Structured JSON, source membership, exact quotes, and duplicate proposals are validated before any drafts are committed. Invalid output fails without saving drafts. Humans still approve requirements and publish baselines.

Provider work uses a 180-second fenced lease, a 120-second RQ job timeout, and a maximum of three attempts for interrupted work. Cancellation invalidates the fence, and authorization is checked before the provider call and again before saving. Provider failures are shown without raw provider text or secrets. A provider error is terminal; submitting again deliberately creates a new job. The real gateway remains blocked by the organization's Free plan.

## Verification boundaries

Unit/integration checks cover duplicate delivery, partial imports, stale previews, project isolation, revoked actors, invalid citations, cancelled extraction, frozen reports, stale links, immutable originals, and simulated queue loss/worker interruption. PostgreSQL checks run only in disposable schemas. The browser journey exercises import/commit/report download and deterministic extraction; its synthetic provider rejects unknown inputs. This is not a model-quality evaluation.

Still required: real Redis/S3/Linux worker interruption tests, live provider extraction, grounded multi-requirement change analysis with lexical/dense/hybrid retrieval, human-reviewed evaluation, broader access/security/accessibility/performance tests, and clean-stack backup/restore verification.

Final checks on 19 October 2026: 45 local backend tests passed (2 PostgreSQL-only skips), 7 Chromium tests passed, and the final focused Neon PostgreSQL run passed 4 tests including complete migration round trips, extraction cancellation/citation validation, and frozen reports. Static checks and the production build passed. The configured production database is at migration 0013. The final schema check was rerun after an earlier test process saw a migration added while its ORM metadata was already loaded.
