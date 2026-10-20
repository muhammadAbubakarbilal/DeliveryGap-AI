# Frontend and backend handoff

The core product now includes bounded source extraction and queued hybrid change analysis. External AI processing is disabled by default and can only be enabled/revoked by a project lead or workspace administrator; all findings remain proposals and require human review. Live-provider and model-quality acceptance are still open, so local synthetic-provider success is not a quality claim.

## Functional submission status

The functional backend/frontend slice is implemented and locally verified. The submission path covers authenticated project work, source upload/manual text, PDF/DOCX/TXT/MD parsing, immutable originals and spans, grounded requirement drafts, revision/approval/baseline workflows, bounded extraction, queued analysis proposals, request decomposition, citation validation, finding decisions, CSV/manual evidence, traceability, frozen Markdown/CSV reports, operation history, cancellation, retry, idempotency, project isolation, role restrictions, and browser loading/error/permission/retry states.

Docker, deployment, backup, and infrastructure rehearsal are intentionally outside this functional submission pass. Their documentation remains reference material; it does not block running the local API/UI tests or presenting the product workflow.

## Connected workflows

1. Sign in, create a project, and manage contributor/reviewer access.
2. Upload a PDF, DOCX, text, or Markdown source, or enter manually authored text. View parsed passages and download the immutable original.
3. Create requirement drafts manually using a selected passage and an exact quote. A lead approves them, can split or merge requirements into cited drafts with immutable lineage, and publishes selected revisions as a baseline. Superseded parents remain in existing baselines but cannot enter future baselines.
4. Record tasks, tests, and pull requests manually, or preview and commit task/test CSV files. Test execution time and environment are stored as structured metadata and retained in artifact history. Download templates from the evidence screen. Custom header mappings are validated before commit; duplicate or ambiguous destinations are rejected. Imported references create proposals rather than accepted links.
5. Review evidence links against the artifact revision inspected. Changes to artifacts make existing links visibly stale. Filter traceability by current, missing, or changed evidence; leads can accept or reject up to 100 links atomically with revision checks.
6. Generate a frozen report for a selected baseline, optionally filtering findings by analysis runs, classification, and reviewer state. Preview it and download Markdown or CSV. The chosen filters and matching findings are frozen in the snapshot; later edits do not alter it.
7. With lead consent enabled, extract cited requirement drafts or queue change analysis. Analysis decomposes input into at most 10 exact, ordered request spans, retrieves and classifies each against approved baseline evidence using BM25 and cached dense embeddings, and retains successful findings if another request fails. The UI shows per-request status, exact source offsets, candidate ranks and citations. Notes without actionable changes complete successfully with no findings. Scores are not confidence values.

Permissions, archived-project checks, idempotent commands, revision checks, failure states, and history are enforced by the API. Next.js supplies the UI and proxy; FastAPI owns domain behavior.

Failed extraction and change-analysis jobs can be retried in place by a contributor while project AI consent remains enabled and the three-attempt budget is not exhausted. Extraction resumes validated batch checkpoints; analysis reruns the frozen input. Retry commands are idempotent, and the UI retains the same key after an ambiguous network failure.

## Required runtime

The existing localhost app uses Neon PostgreSQL and Auth. Private S3-compatible storage is required for source originals. Redis, an RQ worker, and the dispatcher are required for parsing, imports, and reports. The [Compose configuration](../compose.yaml) defines the complete local stack, including a separate local PostgreSQL database. Its accounts and data are separate from Neon unless configuration is explicitly changed.

Docker was unavailable in the development environment during verification. The browser suite uses isolated storage and a test executor; it proves the frontend/API workflow, not live Redis/S3 operation. No fallback silently replaces production infrastructure.

## Still outside completion acceptance

- Real storage/queue interruption and recovery, clean-stack deployment, backup/restore rehearsal.
- Live Redis/RQ retry/lease recovery and concurrent PostgreSQL validation of the new retry transition; local unit tests exercise state and replay semantics, not database locking under real worker contention.
- Broader PostgreSQL concurrency and authorization acceptance, plus comprehensive accessibility/performance/security checks against the full PRD. Earlier disposable Neon checks covered migrations through 0015 and test-metadata paths; migrations 0016/0017 have local SQLite round-trip coverage only and still need a disposable PostgreSQL run.
- Live AI Gateway operation and provider billing/timeout acceptance; the prior Neon setup check was blocked by the organization's Free plan.
- Human review of the proposed ShopFlow labels and a frozen, held-out family evaluation before making quality claims.
- Broader retrieval/performance measurements and validated behavior on human-reviewed multi-action requests.

The latest continuation added an [infrastructure acceptance harness](infrastructure-acceptance.md) and [release runbook](release-runbook.md). All 13 local Chromium tests now pass using reused test sessions without relaxing authentication throttling. A direct PostgreSQL verification attempt failed because the configured database lacks the vector type; CI now provisions a dedicated test extension namespace, but its live execution and remote extension approval remain pending.

The [supervisor demo guide](SUPERVISOR_DEMO.md) documents the prepared 8–10 minute synthetic walkthrough. The local-only [ShopFlow bootstrap](../scripts/seed_supervisor_demo.py) creates its project, parsed source, cited/approved requirement, and B1 through the API; findings and evidence are completed in the UI. The seed script is covered by tests but has not been executed against the real Compose stack because Docker is unavailable.

See the chronological [verification ledger](completion-work.md) for exact test results. This is a handoff of working functionality, not a claim that every PRD release gate has passed.
