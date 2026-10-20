# DeliveryGap AI
## Complete Product Requirements Document + Technical Implementation Blueprint

**Version:** 1.0  
**Date:** 16 October 2026  
**Project type:** Single-workspace internal engineering application / internship capstone  
**Implementation horizon:** 8 weeks, solo developer  
**Technology:** Next.js + FastAPI + PostgreSQL/pgvector + Redis + Python ML  
**Status:** Build-ready specification; estimates and thresholds are proposed engineering targets, not observed results.

---

# 0. Executive implementation brief

## 0.1 One-sentence definition

DeliveryGap AI is an evidence-based review tool that tracks what a software team agreed to build, detects potential changes in later conversations, and relates the approved requirements to development and test artifacts so delivery gaps can be investigated before handover.

## 0.2 The problem to solve

Software projects frequently distribute their truth across scopes of work, PRDs, meeting notes, task trackers, and code repositories. A team can implement something that was discussed but never approved; a requirement can remain untested; two documents can contradict each other. Manual cross-checking becomes repetitive and unreliable. This application centralizes the evidence and proposes findings for human review.

## 0.3 What a user will actually do

1. Sign in and create a project.
2. Upload an approved scope document (PDF, DOCX, TXT or MD).
3. Review, edit, and approve AI-extracted atomic requirements.
4. Freeze these approved requirement versions into **Baseline 1**.
5. Upload subsequent meeting notes or paste a new client request.
6. Run a change analysis against the selected baseline.
7. Open a finding, read source citations, inspect related requirements, and **confirm**, **dismiss**, or **request clarification**.
8. Import task records (CSV) and optionally connect a read-only GitHub repository to discover related pull requests.
9. Attach test evidence or manually record missing evidence; view traceability gaps.
10. Export an evidence-backed review report.

## 0.4 Working product definition (MVP)

The MVP is complete only when an external reviewer can execute the above workflow on a seeded example project, without editing the database or using developer-only endpoints.

## 0.5 Ground rules

- No billing, subscription plans, checkout, CRM, lead generation, marketing pages or pricing flows.
- One workspace, multiple users, per-project roles. **Not** a multi-tenant SaaS.
- No automatic changes to GitHub, Jira, requirements baselines, or code.
- AI generates **proposals with evidence**; a user owns approvals and project decisions.
- Use only synthetic, public, or explicitly authorized project material.
- Lack of evidence is labeled **"evidence not found"**, never **"feature not implemented"**.
- Similarity scores are not calibrated probabilities of correctness.
- Deterministic and repeatable testing matters more than agent autonomy.

# 1. Product scope and priorities

## 1.1 In-scope for the eight-week MVP (P0)

| ID | Feature | Scope | Acceptance criterion |
|---|---|---|---|
| P0-01 | Authentication | Login/logout, admin-seeded users, project membership | Unauthorized request receives 401; non-member receives 403/404 without project data leakage. |
| P0-02 | Projects | Create/list/update projects, members | Authorized member can enter project; removed member loses access. |
| P0-03 | Documents | Upload, parse, status, version, cite | Text PDFs/DOCX/TXT/MD parsed; source reference opens correct page or paragraph. |
| P0-04 | Requirements | AI extraction, review/edit/approve/reject | User can modify extracted text before approval; each approved item retains origin evidence. |
| P0-05 | Baselines | Immutable snapshots of approved requirement versions | Baseline cannot be silently edited; later changes create new versions/new baseline. |
| P0-06 | New requests | Paste text/upload notes, analyze | New input is persisted, analysis is asynchronous, failures are visible. |
| P0-07 | Detection | Candidate requirement retrieval + classification | Each finding has category, cited supporting evidence, reviewer state, run metadata. |
| P0-08 | Findings review | Triage, confirm, dismiss, clarify | Every review decision is saved with actor, time, optional rationale. |
| P0-09 | Task import | CSV of tickets/issues | Imported tasks can be linked to requirements manually or by AI proposal. |
| P0-10 | Delivery links | Candidate PR/task ↔ requirement links | Proposed links and confirmed links are clearly differentiated. |
| P0-11 | Test evidence | Manual entries + CSV import | A requirement can show linked / unlinked test evidence. |
| P0-12 | Project overview | Useful aggregated counts + links | Every count is derived from stored data; no fabricated dashboard statistics. |
| P0-13 | Report | Download Markdown/CSV; PDF as optional stretch | Report includes source links, decision states, generation timestamp, baseline ID. |
| P0-14 | ML evaluation | Labeled data, baseline model, error analysis | Reproducible precision/recall/F1 and retrieval metrics on held-out cases. |
| P0-15 | Reliability | Tests, DB migrations, logging, Docker | `docker compose up` starts services; documented smoke test passes. |

## 1.2 P1 if P0 is stable

- Read-only GitHub pull-request import by manual sync, with repository scoping and minimum permissions.
- Source viewer with side-by-side comparison/highlighting.
- Requirements search and filtering; a clearer traceability matrix.
- Change-order drafting (never automatic client communication).
- Re-run analysis when a newer baseline is published; clearly label older runs stale.

## 1.3 Explicitly excluded / future

- Payment, subscriptions, organizational tenant billing or plan quotas.
- Jira OAuth and two-way syncing; Slack, Teams, email inbox integrations.
- Joining live meetings, live transcription, or real-time meeting assistants.
- Agentic browser actions or autonomously creating/closing tickets.
- Automatically deciding contract status, scope acceptance, estimates or legal obligations.
- Automated code correctness/security review; claiming tests passed based on PR titles.
- OCR for scanned PDFs and images, arbitrary file formats, audio/video processing.
- Full CI test-artifact collection, advanced RBAC, SSO, complex notification engine.
- Configurable multi-workspace SaaS architecture, usage analytics/billing.

## 1.4 Build priority rule

If behind schedule, preserve in this order: **document → approved baseline → new request → detection → reviewed finding → benchmark → report**. Defer GitHub first, then the sophisticated dashboard, then report styling. A finished core workflow outranks broad but broken features.

# 2. Actors, permissions and product vocabulary

## 2.1 Users

| Role | Permissions | Notes |
|---|---|---|
| Workspace admin | Create projects, invite/manage users, configure providers, see projects | One internal workspace only. |
| Project lead | Upload, approve requirements, publish baselines, review findings, manage links, export | May approve project-level decisions. |
| Project member | Upload, propose/edit draft requirements, import tasks, link evidence, view reports | Cannot publish baselines or finalize findings unless explicitly authorized. |
| Read-only reviewer | View project, sources, findings, reports | Cannot modify data. |

Implement `user_id`, `project_id`, `role` membership. Workspace admin may bypass membership checks only deliberately and with an audit trail.

## 2.2 Definitions

- **Source document:** Uploaded file representing a scope/PRD/specification or later communication.
- **Source span:** Exact page/paragraph/character region and quoted text used as evidence.
- **Requirement:** Stable business identifier such as `REQ-001`.
- **Requirement version:** Immutable text and attributes at a particular revision.
- **Approved baseline:** Immutable list of requirement-version IDs defining the agreed reference scope for one analysis.
- **Change input:** New request, meeting note, or later document to compare against a selected baseline.
- **Analysis run:** A reproducible execution referencing input, baseline, model/configuration, and result.
- **Finding:** A proposed classification or evidence gap, with explanation and source references.
- **Decision:** Human review outcome on a finding; never changed implicitly by an AI rerun.
- **Delivery artifact:** Task or GitHub PR containing potential evidence of implementation.
- **Traceability link:** Proposed or human-accepted relationship between a requirement version and a delivery/test artifact.

# 3. Full user journeys / workflow logic

## W1. First-time project setup

**Trigger:** user clicks New Project.  
**Inputs:** name (required), description (optional), repository URL (optional), owner.  
**Sequence:** project row → membership row → empty dashboard.  
**UI states:** form validation, saving, success, failure, no projects.  
**Rule:** identical project names allowed; IDs drive uniqueness.

## W2. Parse and approve source requirements

1. Lead uploads `SOW_v1.pdf`; browser requests upload.
2. Backend validates extension, MIME, size, quota, project access; streams file into private object store and creates `document_version` with SHA-256 hash.
3. DB transaction creates `processing_job(status=queued)` and queues task.
4. Worker extracts text and positions into page/paragraph spans. Store spans, not just a single flat blob.
5. Worker creates semantic chunks, embeddings and extraction prompt batches.
6. LLM returns schema-constrained requirement candidates; backend validates the schema and source citations.
7. Candidate entries are stored as **drafts**, not approved scope; extraction warnings remain visible.
8. Reviewer edits/splits/merges/rejects candidates; corrects acceptance criteria.
9. Lead approves individual requirement revisions.
10. Lead creates immutable baseline `B1` from selected approved revisions; record actor/timestamp.

**Failure cases:** no extractable text → `needs_manual_input`; provider unavailable → retriable job; invalid AI output → `needs_review` with error (never silent success); duplicate file hash → allow versioning with warning.

## W3. Detect a new change

1. Reviewer pastes note: *Client wants checkout in EUR, GBP and USD, including automatic conversion.*
2. Choose baseline `B1`; click Analyze.
3. Backend persists change input and run `queued` atomically; worker begins.
4. Worker identifies one or several distinct atomic requests (avoid comparing an entire long meeting transcript as one request).
5. For each atomic request, retrieve candidate baseline requirements using keyword + vector search; rerank the top candidates.
6. Classifier receives **only** selected relevant approved requirements, new request, and grounded source spans. It may return `IN_SCOPE`, `POTENTIAL_SCOPE_ADDITION`, `CONFLICT`, `AMBIGUOUS`, or `INSUFFICIENT_EVIDENCE`.
7. Validate that every citation maps to actual stored spans. Unsupported citations are removed and finding is downgraded to `INSUFFICIENT_EVIDENCE`.
8. Save findings with explanation, candidate links, source evidence and model/config IDs; mark run succeeded/partial/failed.
9. Reviewer compares new request to baseline and confirms, dismisses or seeks clarification.

**Important:** `POTENTIAL_SCOPE_ADDITION` means *not sufficiently supported by the stored baseline*, not a legal or contractual determination.

## W4. Build traceability

1. Import tasks CSV (`external_id`, `title`, `description`, `status`, `url`, optionally `requirement_id`).
2. Import test CSV (`test_id`, `name`, `result`, `executed_at`, `related_requirement_id`, `url`).
3. System suggests links by matching issue/PR content to requirement text using retrieval + reranker.
4. Reviewer accepts/rejects links. Confirmed links are retained independently from later AI reruns.
5. For a requirement, show: relevant tickets, candidate PRs, linked tests and statuses.
6. Missing linked test evidence becomes a **coverage gap**. Display "No linked test evidence recorded", not "Untested code".

## W5. Publish a changed scope baseline

1. User records a confirmed scope change and creates revised requirement draft(s).
2. Reviewer approves new requirement versions; prior versions remain immutable.
3. Lead publishes `B2` containing a new list of approved versions.
4. Old `B1` runs retain their exact input and baseline linkage; UI flags them as based on an older baseline.
5. No automatic rebasing or silent mutation of findings.

## W6. Export delivery review

Choose baseline, review date, finding statuses and include/exclude unreviewed AI proposals. Backend builds deterministic report from DB. Output shows approved scope, discovered potential changes, reviewer decisions, traceability and unresolved gaps, citations, and a note explaining non-verified AI classifications.

# 4. Product screens / frontend specification

Use **Next.js App Router + TypeScript + Tailwind CSS + accessible component primitives (e.g., shadcn/ui)**. Server components for initial authenticated read views; client components for upload controls, tables, forms and side panels. Call the FastAPI API through a typed client; do not duplicate AI/business logic in Next.js. Keep sensitive authenticated responses uncached (`no-store`).

| Route | Screen | Components | Main actions | Loading/empty/error |
|---|---|---|---|---|
| `/login` | Sign in | email, password, message | login/logout | bad credentials, expired session |
| `/projects` | Project list | search, project cards, new modal | create, open | empty CTA, load error |
| `/projects/[id]` | Overview | findings by status, latest runs, baseline, activity | drill down | no baseline guide |
| `/projects/[id]/documents` | Documents | table, upload zone, parse progress | upload, version, inspect | unsupported/scanned file |
| `/projects/[id]/documents/[docId]` | Document details | source viewer, parsing status, candidates | preview, retry | extraction error |
| `/projects/[id]/requirements` | Requirements register | filterable table, status, source, reviewer | edit, approve, reject | draft list empty |
| `/projects/[id]/requirements/[reqId]` | Requirement details | versions, attributes, source evidence, links | edit new version, view history | superseded warning |
| `/projects/[id]/baselines` | Baselines | versions, requirement count, current badge | publish baseline, compare | no approved reqs |
| `/projects/[id]/analyze` | New change analysis | paste/upload, baseline select, job state | analyze | no baseline; partial run |
| `/projects/[id]/runs/[runId]` | Analysis results | run metadata, grouped findings, filters | open finding, rerun | none found; failure state |
| `/projects/[id]/findings/[id]` | Finding detail | side-by-side source citations, classification, reviewer controls | confirm/dismiss/clarify | stale baseline note |
| `/projects/[id]/traceability` | Coverage matrix | requirements rows, task/PR/test links, gaps | accept/reject links, import | evidence unknown |
| `/projects/[id]/integrations` | Imports / GitHub | CSV import, repository settings, sync status | import, sync | insufficient permissions |
| `/projects/[id]/reports` | Reports | baseline filters, report preview | generate/download | nothing to report |
| `/projects/[id]/settings` | Project access | members and roles | add/remove/update | unauthorized |

### 4.1 Page-level UI behavior

**Overview:** show five cards: Approved requirements, Open findings, Confirmed changes, Requirements lacking linked test evidence, Most recent analysis. Each metric links to filtered records. A count must be explicitly scoped to a baseline and never imply delivery correctness.

**Documents:** support drag-and-drop and file picker, maximum 10 MB/file for prototype, extension/MIME validation, upload progress, checksum warning, status chips (`uploaded/queued/processing/ready/needs_manual_input/failed`). Detailed page should show extracted text and source positions; use page-based anchors for PDFs and paragraph anchors for DOCX/MD.

**Requirements:** table columns ID, title, priority, state, source, version and reviewer. Side panel/edit form fields: title, description, acceptance criteria (repeatable), type, source quote, notes. Approve one, bulk approve optional. Publishing baseline is an explicit separate action with confirmation.

**Analyze:** input text box + file source selector, choice of current or past baseline, optional model configuration, submit. Progress may be polled every 2–3 seconds; no WebSocket requirement. No duplicate runs on double-click (`Idempotency-Key`).

**Findings:** group by classification and reviewer state, search, summary and cited excerpts. Details show (a) new request snippet, (b) relevant approved requirement(s), (c) AI explanation, (d) evidence, (e) review decision. If the evidence is weak, the UI must say so prominently. "Confidence" is not shown as a probability unless calibrated; expose retrieval score only as debug metadata.

**Traceability:** columns Req ID, requirement, tasks, PRs, tests, link-review state. Filter for `no linked tests`, `unreviewed links`, `stale artifacts`. Clicking opens source. Link acceptance should have undo/rejection and audit.

**Reports:** include review watermark `Generated <timestamp>; Baseline Bx; Contains proposed AI findings requiring human verification`. Exports must not include secrets or raw access tokens.

### 4.2 Reusable frontend components

`AppShell`, `ProjectSwitcher`, `Breadcrumbs`, `StatusBadge`, `DocumentUploader`, `JobProgress`, `SourceCitation`, `EvidencePanel`, `RequirementEditor`, `BaselineSelector`, `FindingCard`, `DecisionActions`, `TraceabilityTable`, `ImportWizard`, `EmptyState`, `ApiErrorBoundary`, `ConfirmDialog`, `SkeletonRow`, `ToastProvider`.

### 4.3 Accessibility / performance

Keyboard-accessible decisions/forms; visible focus, WCAG-oriented contrast, labels for input, accessible tables, responsive design. Use pagination for lists (default 25 rows), server-side filtering, defer heavy source previews until opened, and code-split large visualizations. Treat docs/requirements as sensitive; avoid browser persistence for document contents.

# 5. Backend service architecture

**FastAPI is the authoritative application/backend layer.** Next.js only renders UI and calls API. No duplicated domain rules in frontend.

| Module | Responsibility | Inputs → outputs |
|---|---|---|
| `auth` | verify password/session, membership and role checks | credentials → authenticated principal |
| `projects` | projects, memberships | user commands → persisted changes |
| `documents` | upload validation, metadata, versioning, source extraction | file → document version, extracted spans |
| `requirements` | candidate management, versioning, approval | extracted drafts → approved revisions |
| `baselines` | freeze and list immutable requirement-version snapshots | approved versions → baseline |
| `change_inputs` | ingest new requests or notes | text/file → immutable input |
| `analysis` | orchestrate extraction, retrieval, classification, evidence validation | input + baseline → proposed findings |
| `findings` | lifecycle + human decisions | reviewed finding → decision log |
| `integrations` | GitHub sync and CSV task/test import | external metadata → artifacts |
| `traceability` | recommend and review requirement ↔ artifact links | candidates → accepted/rejected links |
| `reports` | deterministic read-only exports | baseline + findings → Markdown/CSV |
| `evaluation` | offline benchmark datasets and runs | labeled cases → metrics and failures |
| `jobs` | enqueue, retry, status and worker idempotency | task invocation → job state |
| `audit` | append-only event records | actor + action + target + changes |

### 5.1 Layering

`api/routes` (HTTP validation) → `services` (use cases / permission guards) → `repositories` (SQLAlchemy) → database. AI inference is through `ai/providers`, `ai/retrieval`, and `ai/pipelines`, never imported directly into route handlers. Worker handlers invoke the **same domain services** as API operations, but under explicit system identity and project scope.

### 5.2 Jobs and state machine

Job states: `queued → running → succeeded | partial | failed`; `failed → queued` only through explicit retry after max attempts/retryable error check. Worker stores `started_at`, `completed_at`, `attempts`, `progress`, `error_code`, `safe_error_message`, `model_version`, `config_hash`. Redis holds queue data; PostgreSQL holds authoritative job state. Redis alone is never the source of truth.

Use Redis + **RQ** for a simple first implementation, or Celery if familiar. Don't use FastAPI in-process `BackgroundTasks` for document extraction/ML inference: worker restarts and long jobs require durable-ish queue handling. Configure retries/backoff and dead-letter/failure visibility. Redis queue persistence and reconciliation on restarts must be addressed (at-least-once processing; idempotent handlers).

### 5.3 Auth pattern

For solo MVP: backend-managed login, Argon2 password hashes, short-lived access session in HttpOnly + Secure + SameSite cookie plus CSRF protection for mutating cookie-authenticated endpoints. Session table supports logout/revocation. Simplify user onboarding with admin-created users; no public signup or password reset email. All project queries must include authorization checking. Do not expose API tokens to browser. On production frontend/backend split, choose same-site domain strategy and configure CORS/CSRF carefully.

### 5.4 Backend error envelope

Every non-2xx response uses: `{ "error": { "code": "SOURCE_NOT_EXTRACTABLE", "message": "No selectable text detected", "request_id": "...", "details": {} } }`. Avoid leaking exception traces or provider outputs. Common statuses: 400 invalid state, 401 unauthenticated, 403 permission, 404 hidden/not found, 409 stale baseline/idempotency conflict, 413 oversized upload, 422 validation, 429 request/provider limits, 503 dependency unavailable.

# 6. API contract (prefix `/api/v1`)

Specify request/response schemas in Pydantic, generate OpenAPI and use a typed frontend client. UUIDs are opaque. All `POST` routes changing state support idempotency where retries are possible.

| Method | Endpoint | Input | Output / behavior |
|---|---|---|---|
| POST | `/auth/login` | email, password | sets secure session cookie; user JSON |
| POST | `/auth/logout` | none | revokes session |
| GET | `/auth/me` | none | current user, project roles |
| GET/POST | `/projects` | filters / `{name, description}` | list / project |
| GET/PATCH | `/projects/{p}` | fields | project detail/update |
| GET/POST/DELETE | `/projects/{p}/members` | user+role / user ID | membership management |
| POST | `/projects/{p}/documents` | multipart file, category | document ID, job ID, status 202 |
| GET | `/projects/{p}/documents` | page/filter | document versions |
| GET | `/projects/{p}/documents/{d}` | none | metadata, processing state |
| GET | `/projects/{p}/documents/{d}/spans` | page/paragraph cursor | source spans |
| POST | `/projects/{p}/documents/{d}/retry` | none | new/restarted job |
| GET | `/projects/{p}/requirements` | filters/page | requirement current states |
| POST | `/projects/{p}/requirements` | manual candidate | draft requirement |
| GET | `/projects/{p}/requirements/{r}` | none | revisions and provenance |
| POST | `/projects/{p}/requirements/{r}/versions` | edited draft content | new version |
| POST | `/projects/{p}/requirements/{r}/approve` | version ID | approves that version |
| POST | `/projects/{p}/requirements/{r}/reject` | reason | rejects draft candidate |
| GET/POST | `/projects/{p}/baselines` | list / selected approved version IDs | immutable baseline |
| GET | `/projects/{p}/baselines/{b}` | none | snapshot and membership |
| POST | `/projects/{p}/change-inputs` | text/document version | persisted input ID |
| POST | `/projects/{p}/analysis-runs` | input ID, baseline ID, config ID | run/job IDs, 202 |
| GET | `/projects/{p}/analysis-runs/{run}` | none | run state, findings summary |
| GET | `/projects/{p}/findings` | filters, baseline/run | findings list |
| GET | `/projects/{p}/findings/{f}` | none | classification, citations, review |
| POST | `/projects/{p}/findings/{f}/decisions` | decision, reason | append-only decision event/current state |
| POST | `/projects/{p}/imports/tasks` | CSV | import results/job ID |
| POST | `/projects/{p}/imports/tests` | CSV | import results/job ID |
| POST | `/projects/{p}/github/connect` | repo ID, token reference | saved read-only configuration |
| POST | `/projects/{p}/github/sync` | since cursor | queued sync job |
| GET | `/projects/{p}/artifacts` | type/filter | imported task/PR/test metadata |
| GET | `/projects/{p}/links` | filters | proposed/accepted trace links |
| POST | `/projects/{p}/links/{id}/review` | accept/reject/reason | new review state |
| GET | `/projects/{p}/traceability` | baseline ID | requirements + link/coverage rows |
| POST | `/projects/{p}/reports` | baseline, filters, format | download or report job |
| GET | `/projects/{p}/jobs/{job}` | none | status, progress and safe error |
| GET | `/health/live` | none | liveness only |
| GET | `/health/ready` | none | DB/queue health (protected operational detail as needed) |

**Implementation choice:** Report/download could be `GET` with query params but `POST` accommodates more filter structure; never write server-side files outside private temp storage. Repository/webhook integrations are optional: for initial P0, manual CSV import is the guaranteed workflow.

### 6.1 Representative analysis request/response

```json
POST /api/v1/projects/{project_id}/analysis-runs
{
  "change_input_id": "uuid",
  "baseline_id": "uuid",
  "configuration_id": "default-v1"
}
```

```json
HTTP 202
{
  "run_id": "uuid",
  "job_id": "uuid",
  "status": "queued"
}
```

### 6.2 Representative finding

```json
{
  "id": "uuid",
  "run_id": "uuid",
  "request_text": "Support EUR, GBP and USD at checkout.",
  "classification": "POTENTIAL_SCOPE_ADDITION",
  "explanation": "Baseline REQ-014 mentions a single checkout currency.",
  "review_status": "pending",
  "requirement_refs": ["REQ-014"],
  "evidence": [
    {"source_span_id":"uuid","side":"baseline","quote":"Checkout uses USD only."},
    {"source_span_id":"uuid","side":"new_input","quote":"Support EUR, GBP and USD."}
  ],
  "warnings": ["AI classification requires human review"]
}
```

# 7. Data model / PostgreSQL schema

**Core principles:** UUID primary keys; UTC timestamps; explicit foreign keys; unique constraints; indexes for project scope and state; audit-sensitive rows append-only; migration-driven schema (Alembic). Store original binaries in object storage, **not in PostgreSQL**. Store only references/checksums in DB. Use JSONB for bounded flexible attributes, not for the entire domain model.

## 7.1 Identity and workspace

| Table | Important fields | Keys / notes |
|---|---|---|
| `users` | `id`, `email`, `password_hash`, `display_name`, `is_active`, timestamps | unique normalized email |
| `sessions` | `id`, `user_id`, `token_hash`, `expires_at`, `revoked_at`, created | rotate/revoke, never store raw session token |
| `projects` | `id`, `name`, `description`, `owner_id`, `status`, timestamps | status active/archived |
| `project_members` | `project_id`, `user_id`, `role`, created | composite unique project/user |

## 7.2 Documents and provenance

| Table | Important fields | Keys / notes |
|---|---|---|
| `documents` | `id`, `project_id`, `logical_name`, `category`, `created_by`, created | container for revisions |
| `document_versions` | `id`, `document_id`, `version_number`, `filename`, `mime_type`, `sha256`, `storage_key`, `status`, `byte_size`, `uploaded_at` | unique document/version; immutable binary |
| `source_spans` | `id`, `document_version_id`, `page_no`, `paragraph_no`, `char_start`, `char_end`, `text`, `location_meta` | document-dependent position; no invented page numbers |
| `document_chunks` | `id`, `document_version_id`, `chunk_index`, `text`, `token_count`, `source_span_ids`, `embedding` (`vector(384)`), `textsearch` | indexes by doc/version; embedding model pinned |

For a pasted change request, source spans may reference a separate `change_inputs` text payload, so make the provenance representation **polymorphic but validated** (source kind + source ID), or normalize source text into an internal synthetic document version. **Recommended simplest implementation:** treat pasted text as synthetic `document_version` with a textual `source_span`, so all citations resolve through the same mechanism.

## 7.3 Requirements and immutable baselines

| Table | Important fields | Keys / notes |
|---|---|---|
| `requirements` | `id`, `project_id`, `human_code`, `created_by`, `created_at`, `current_version_id` | unique (`project_id`, `human_code`), e.g. REQ-014 |
| `requirement_versions` | `id`, `requirement_id`, `version_number`, `title`, `description`, `acceptance_criteria` JSONB, `priority`, `kind`, `status`, `created_by`, timestamps | immutable once approved; statuses draft/approved/rejected/superseded |
| `requirement_sources` | `requirement_version_id`, `source_span_id`, `support_type`, `quoted_text` | multiple origins per requirement; source must exist |
| `baselines` | `id`, `project_id`, `label`, `version_number`, `published_by`, `published_at`, `notes` | immutable snapshot header |
| `baseline_items` | `baseline_id`, `requirement_version_id` | only approved revisions, unique composite; cannot change after publish |

**Rule:** Editing an approved requirement creates a *new draft version*. Baseline B1 always references its original approved version. B2 references revised versions after approval. Prevent two different versions of the same requirement in one baseline.

## 7.4 Analysis, findings and reviews

| Table | Important fields | Keys / notes |
|---|---|---|
| `change_inputs` | `id`, `project_id`, `document_version_id`, `title`, `submitted_by`, `created_at` | source of candidate change text |
| `analysis_runs` | `id`, `project_id`, `change_input_id`, `baseline_id`, `status`, `config_hash`, `model_name`, `started_at`, `ended_at`, `error_code`, `created_by` | historical immutable config linkage |
| `atomic_requests` | `id`, `analysis_run_id`, `text`, `source_span_ids`, `sequence_index` | splitter outputs with provenance |
| `findings` | `id`, `analysis_run_id`, `atomic_request_id`, `classification`, `explanation`, `review_status`, `severity_hint`, `created_at` | category is AI proposal, severity heuristic not certainty |
| `finding_evidence` | `id`, `finding_id`, `source_span_id`, `requirement_version_id`, `side`, `quote`, `evidence_type` | validation ensures quote/span alignment |
| `finding_decisions` | `id`, `finding_id`, `decision`, `reason`, `reviewed_by`, `created_at` | append-only; latest decision determines current status |

Finding `review_status`: `pending`, `confirmed`, `dismissed`, `clarification_requested`. Classification: `IN_SCOPE`, `POTENTIAL_SCOPE_ADDITION`, `CONFLICT`, `AMBIGUOUS`, `INSUFFICIENT_EVIDENCE`. A persisted `review_status` may be denormalized from latest decision but must update transactionally.

## 7.5 Delivery artifacts and traceability

| Table | Important fields | Keys / notes |
|---|---|---|
| `external_connections` | `id`, `project_id`, `provider`, `repository_full_name`, `credential_secret_ref`, `last_sync_at`, `status` | secrets in secret store / encrypted at rest; never raw in DB |
| `delivery_artifacts` | `id`, `project_id`, `provider`, `kind`, `external_id`, `title`, `description`, `url`, `status`, `updated_at`, `raw_safe_metadata` | unique by project/provider/kind/external ID; kinds task/pr/test |
| `artifact_links` | `id`, `project_id`, `requirement_version_id`, `artifact_id`, `relation_type`, `origin`, `review_status`, `reviewed_by`, `reviewed_at` | origin manual/model, state proposed/accepted/rejected |
| `test_evidence` | optional separate table if test CSV needs `executed_at`, `result`, `environment` beyond `delivery_artifacts` | can be represented by artifact kind `test` for simpler MVP |

Recommended MVP uses `delivery_artifacts(kind=test)` with `test_result` in typed columns or validated JSONB. Do not treat an imported issue's `status=done` as proof of implementation and do not infer a test pass from PR text.

## 7.6 Operations and evaluation

| Table | Important fields | Keys / notes |
|---|---|---|
| `processing_jobs` | `id`, `project_id`, `job_type`, `object_type`, `object_id`, `status`, `progress`, `attempts`, `error_code`, `created_at`, `started_at`, `completed_at` | queue source-of-truth metadata |
| `audit_events` | `id`, `project_id`, `actor_id`, `event_type`, `target_type`, `target_id`, `before_json`, `after_json`, `created_at` | immutable application log |
| `evaluation_cases` | `id`, `dataset_split`, `baseline_fixture_id`, `input_text`, `expected_class`, `relevant_requirement_codes`, `gold_evidence_span_ids`, `notes` | gold labels reviewed by person |
| `evaluation_runs` | `id`, `dataset_version`, `config_hash`, `model_name`, `started_at`, `completed_at`, `metrics_json` | per-experiment metrics |
| `evaluation_case_results` | `run_id`, `case_id`, `predicted_class`, `retrieved_codes`, `latency_ms`, `error`, `details_json` | reproducible per-case audit |

## 7.7 Database indexes and integrity

- `project_members(project_id, user_id)` unique; user email unique case-insensitively.
- `documents(project_id, created_at)`, `requirements(project_id, human_code)`, `findings(analysis_run_id, review_status)`, `delivery_artifacts(project_id, kind, updated_at)`.
- Full text GIN index on `document_chunks.textsearch`; pgvector cosine index only after validating data volumes (small corpus may perform better with exact search).
- Foreign keys prevent cross-project linking; service layer *also* checks both objects belong to the same project.
- Use `version`/optimistic update check on concurrently edited drafts and finding reviews.
- Unique `analysis_runs` idempotency key per caller/request; job payloads contain only persistent IDs, not raw secret-bearing documents.
- Soft archive of projects; avoid deleting historical baseline/evaluation references during MVP.

# 8. Detailed AI/ML architecture

## 8.1 Pipeline A: document extraction

```
File upload
  -> file validation / checksum
  -> text extraction into source spans
  -> cleaning without losing source offsets
  -> logical chunking with overlap
  -> embedding generation
  -> AI requirement-candidate extraction
  -> strict schema validation
  -> source-citation verification
  -> draft requirements for human review
```

**Parsing:** `pypdf` for selectable-text PDF, `python-docx` for DOCX, built-in text decoders for TXT/MD. PDF extraction of tables may be imperfect. Detect sparse/empty extraction and ask for manual text, not hallucinated OCR. For original PDF page anchors, page numbering must derive from parser output (not heuristic splitting). Consider a suitable open-source PDF viewer in frontend; implementation can initially show extracted page text instead of browser PDF rendering.

**Chunking:** start with ~400–700 tokens and 80–120 overlap; split by headings/paragraphs before hard token boundaries. These are starting hyperparameters, benchmark rather than assume optimal. Store source span IDs on every chunk.

## 8.2 Pipeline B: structured requirement extraction

Prompt inputs: bounded source chunks + span IDs + extraction schema + refusal to invent. Output must be parsable via Pydantic; rejection/retry if malformed. Extract atomic requirements rather than merging independent commitments.

```json
{
  "requirements": [
    {
      "title": "Single-currency checkout",
      "description": "Checkout totals are displayed and charged in USD.",
      "acceptance_criteria": ["All displayed totals use USD."],
      "type": "functional",
      "priority": "unspecified",
      "source_span_ids": ["actual-span-uuid"],
      "quoted_evidence": ["Checkout is USD only."],
      "uncertainties": []
    }
  ]
}
```

Back-end postprocessors must verify every span ID exists in **the same source document**, quoted text is present/closely aligned to span text, no extra fields, bounded text lengths. Outputs without valid grounding become warnings for manual review, not approved requirements.

## 8.3 Pipeline C: change analysis (core ML feature)

**Step 1: atomic request splitter.** From a later meeting note, create 1..N clearly distinct requested changes with source span ID. Keep original wording; no silent paraphrasing that changes business meaning.

**Step 2: candidate retrieval.** For each atomic request: (a) PostgreSQL full-text BM25-like lexical baseline (Postgres `ts_rank_cd` is not BM25; label it PostgreSQL FTS), (b) vector cosine similarity against approved baseline requirement embeddings, (c) Reciprocal Rank Fusion (RRF) of results, (d) optional cross-encoder rerank top 10 into top 5. **Filter candidates to requirement-version IDs in the selected baseline before ranking**. Do not retrieve requirements from another project or current drafts.

**Step 3: classification.** LLM receives atomic request and a small list of retrieved approved requirement versions with exact citations. Instructions: never infer contract status; use `INSUFFICIENT_EVIDENCE` when missing context; cite only supplied span IDs; separate extracted evidence from inference.

**Step 4: rule validation.** Verify citations, constraint consistency, output enum, max evidence count, reasonable token boundaries. `CONFLICT` requires evidence of mutually incompatible conditions, not just absence. `POTENTIAL_SCOPE_ADDITION` requires plausible novelty relative to retrieved scope and should carry caveat that retrieval may miss other baseline provisions. If no evidence or retrieval coverage is weak, `INSUFFICIENT_EVIDENCE`.

**Step 5: persist.** Save run config hash, model/provider version, retrieval candidates, classification, source spans, warnings and processing latency. Do not overwrite previous run results.

**Step 6: reviewer decision.** Human action is authoritative. Feedback is stored for later labeled evaluation, but user feedback is not automatically treated as ground truth without review.

### 8.3.1 Model configuration

- Sentence embeddings MVP: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions), pinned model revision and license review; validate on English-only samples.
- Reranker: `cross-encoder/ms-marco-MiniLM-L6-v2` or similarly supported model; run on top-k rather than all requirements.
- LLM extraction/classification: provider adapter (`LLMProvider`) with one configured hosted provider + deterministic fixture/mock mode; use environment-provided API key, strict timeout, backoff and cost logging.
- No model training required for MVP; compare approaches empirically. Optional fine-tuning only if gold data and time justify it.
- Provider adapter should expose `extract_requirements`, `split_requests`, `classify_change`; business services do not know provider SDK types.

### 8.3.2 Example decision rules

| Case | Classification to propose | Reason |
|---|---|---|
| Scope explicitly specifies USD-only, later note requests GBP/EUR | `CONFLICT` or `POTENTIAL_SCOPE_ADDITION` depending on the exact original constraint | explicit evidence; reviewer determines contractual treatment |
| Scope includes multi-currency, note asks to implement it | `IN_SCOPE` | matching approved requirement exists |
| Note says “improve checkout” with no details | `AMBIGUOUS` | insufficient specificity |
| Unrelated discussion “team will meet next Tuesday” | No actionable finding or `INSUFFICIENT_EVIDENCE` depending on pipeline policy | not a feature request |
| RAG retrieves no relevant approved scope | `INSUFFICIENT_EVIDENCE` | absence of retrieval evidence does not prove scope addition |

## 8.4 Pipeline D: traceability recommendations

Compare requirement version text to task/PR/test title, description and metadata. Retrieval creates candidate links; reranker/LLM may explain why. Store link as `proposed`. Only user action changes to `accepted` or `rejected`. Imported test results remain unverified external metadata, not attestations. For PRs, never send full private diffs to a hosted LLM unless explicitly authorized; start with title/body and linked issue references. Show exact artifact URL.

## 8.5 Evaluation: what gets measured

Prepare a labeled dataset of **100–150 reviewed examples**, including 25–35% tricky negatives or ambiguous cases. Partition by *project/document*, not random paragraphs, to prevent leakage. Initial suggested split: 60% development, 20% validation, 20% held-out test. For very limited sample sizes, report uncertainty and avoid overclaiming.

**Task A — Retrieval:** Recall@3/5, MRR, NDCG@5, and query latency. Compare lexical-only, dense-only, hybrid, hybrid+rerank.

**Task B — Change classification:** Per-class precision/recall/F1, macro-F1, confusion matrix, false positive rate for potential changes, abstention coverage/accuracy.

**Task C — Extraction:** Human-verified requirement precision/recall on sample documents, supported-source-citation rate, schema-validity rate. Extraction recall requires annotated source requirements, not just checking extracted text.

**Task D — Traceability:** Precision@k on candidate requirement ↔ artifact links and human acceptance rate.

**Task E — Operations:** p50/p95 run latency, LLM input/output token count, errors per run, queue retry count, and rough provider cost estimate using recorded token usage (if prices are applicable).

**Release criteria:** No secret leaks/cross-project access; fully traceable baseline; >95% schema-valid outputs after validation/retry (target); all showcased findings cite real spans; classification improvement over a recorded baseline or documented failure analysis; all P0 smoke tests passing. Statistical quality thresholds are **provisional targets** until actual benchmark difficulty is established; never fabricate results.

**Evaluation validity:** Labelers should use an explicit rubric; adjudicate disagreements, freeze test split before final model tuning, report sample sizes and confidence intervals where feasible, preserve hard cases, and compare against simple baselines to demonstrate ML added value.

## 8.6 AI prompt-injection and untrusted-data handling

Uploaded documents, meeting notes, task titles and PR descriptions are **untrusted content**. Never allow text inside them to override system instructions, call tools, access credentials or mutate DB. Prompts must strongly separate data from task instructions; outputs are schema-validated; tools are not exposed to extracted text. Never use model output as SQL or OS command. Source excerpts are escaped and safely rendered to avoid XSS.

# 9. Import and GitHub integration

## 9.1 Guaranteed P0: CSV imports

Task CSV required columns: `external_id,title,description,status`; optional `url,updated_at,requirement_id`. Test CSV: `test_id,name,result,executed_at` optional `requirement_id,url`. Import preview shows mapping, duplicates, failures, and counts before commit. Upsert by project/provider/kind/external ID. Import report records rejected rows with reasons; partial imports explicit.

## 9.2 P1: GitHub read-only PR sync

**Authentication:** narrow-scope token kept server-side, prefer GitHub App installation if implementation time permits; for demo a fine-grained read-only token on one repository, never committed into source or shown in frontend. Validate repository identity, sanitize URLs and constrain remote requests to GitHub API to avoid SSRF. Fine-grained pull-request read permissions suffice for PR metadata; file content needs additional permitted scopes if used.

**Sync sequence:** user configures repo → backend credential check → worker calls paginated REST API for PRs → upsert by external ID → record last sync cursor and rate limit/backoff → propose links to baseline requirements → reviewer accepts or rejects. **Do not** infer code behavior from PR description; optional diff-level analysis is future scope.

**Webhook:** defer initially; if enabled later, verify GitHub `X-Hub-Signature-256` HMAC signature, deduplicate delivery IDs and avoid running ML directly inside webhook handler.

# 10. Component-by-component interaction

```text
Browser / Next.js
    |
    | HTTPS + authenticated API calls
    v
FastAPI REST API ------------- PostgreSQL + pgvector
    |                                    ^
    | store file metadata                | authoritative records
    v                                    |
Private object storage                     |
    ^                                    |
    | load uploaded binary               |
    |                                    |
Redis queue ----> Python worker ----------+
                    |    |    |
                    |    |    +--> embedding + reranker
                    |    +-------> LLM provider adapter
                    +------------> GitHub read-only API / CSV parser
```

### 10.1 Responsibility table

| Component | Stores | Computes | Must NOT do |
|---|---|---|---|
| Next.js | ephemeral UI state | forms, display, client filtering | business rules, secrets, LLM API calls |
| FastAPI | writes via repositories | permissions, validation, orchestration, report requests | long synchronous AI jobs |
| PostgreSQL | domain records, source text spans, vectors, run history | joins, filtering, text/vector search | binary attachments, API secrets |
| Object storage | original documents, optional exported artifacts | binary retrieval | relational authority |
| Redis | job queue/caching | queue delivery | authoritative job/history state |
| Python worker | no local persistent state | parsing, embeddings, inference, evaluation, sync | unreviewed project decisions |
| External LLM API | provider logs under provider terms | bounded generation/classification | direct access to DB or credentials |
| GitHub API | remote PR metadata | upstream repository data | changed by this application |

### 10.2 Atomic persistence and consistency

For `upload`, reserve DB document/job IDs and storage key, complete upload, then enqueue with retry reconciliation; avoid DB rows pointing indefinitely to absent binaries. For `analyze`, commit run+job before enqueue, then worker claims idempotently. Worker checks whether it already completed a job before writing duplicate findings. Use transactions for baseline creation and review decisions. A database failure leaves job failed; frontend can retry explicitly.

# 11. Repository layout / development convention

```text
deliverygap-ai/
├── apps/
│   ├── web/                         # Next.js App Router
│   │   ├── app/(auth)/login/
│   │   ├── app/(app)/projects/[projectId]/
│   │   │   ├── documents/ requirements/ baselines/
│   │   │   ├── analyze/ runs/ findings/
│   │   │   ├── traceability/ reports/ settings/
│   │   ├── components/             # app shell, tables, evidence UI
│   │   ├── features/               # one folder per domain
│   │   ├── lib/api/                # typed FastAPI client
│   │   └── tests/
│   └── api/
│       ├── app/main.py
│       ├── app/api/v1/routes/
│       ├── app/core/               # config, auth, errors
│       ├── app/models/             # SQLAlchemy
│       ├── app/schemas/            # Pydantic contracts
│       ├── app/repositories/
│       ├── app/services/
│       ├── app/ai/providers/
│       ├── app/ai/pipelines/
│       ├── app/ai/retrieval/
│       ├── app/workers/            # RQ jobs
│       ├── app/integrations/github/
│       ├── alembic/               # migrations
│       └── tests/                 # unit/integration/security
├── datasets/
│   ├── synthetic_project/          # reproducible demo fixture
│   └── eval/                       # labeled train/dev/test + rubrics
├── scripts/
│   ├── seed_demo.py
│   ├── run_eval.py
│   └── smoke_test.py
├── infrastructure/
│   ├── docker-compose.yml
│   ├── api.Dockerfile
│   └── worker.Dockerfile
├── docs/
│   ├── architecture.md
│   ├── api-contracts.md
│   ├── decisions.md
│   ├── evaluation.md
│   └── deployment.md
├── .github/workflows/ci.yml
├── .env.example
└── README.md
```

**Code practices:** Python type hints, `ruff`, `pytest`; TypeScript `strict`, ESLint and unit tests; OpenAPI generated API contract; Alembic migration per schema change; clear PRs and architectural decision records (ADRs). No hard-coded credentials. Pin dependencies with committed lockfiles and document model revisions.

# 12. Infrastructure / running locally and deploying

## 12.1 Local Docker services

- `web`: Next.js at localhost:3000 (optional run via pnpm dev outside Docker for faster iteration).
- `api`: FastAPI/Uvicorn at localhost:8000.
- `worker`: RQ worker process, same codebase, separate container.
- `postgres`: PostgreSQL with pgvector extension at internal 5432.
- `redis`: Redis on internal 6379.
- `minio`: local S3-compatible storage for development; use managed private object storage in deployment.

Start dependencies with `docker compose up -d postgres redis minio`, run Alembic upgrades, seed demo users/project, start API and worker, then start Next.js. Full `docker compose up --build` must be supported by final week.

## 12.2 Production-like demo deployment

Prefer: static/SSR Next.js host as supported, separately deployed containerized FastAPI and worker, managed PostgreSQL/pgvector, managed Redis, private object storage. This avoids attempting to run an always-on queue worker inside a serverless request function. The application must also remain fully demonstrable locally if cloud hosting budget is constrained.

**Secrets:** `DATABASE_URL`, `REDIS_URL`, `SESSION_SECRET`, `LLM_API_KEY`, `LLM_PROVIDER`, `EMBEDDING_MODEL`, `OBJECT_STORAGE_*`, `GITHUB_TOKEN` (optional), `ALLOWED_ORIGINS`, `PUBLIC_APP_URL`. `.env.example` contains placeholders only. Use secret manager or deployment environment for actual values.

## 12.3 Logging and observability

Use correlation `request_id` and `job_id` in structured JSON logs; record stage timing and sanitized errors; never log full confidential document bodies or tokens. Minimum counters: uploads, parse failures, analysis successes/failures, model call failures, job retry count, last sync time. Include a lightweight admin job-status view or API rather than elaborate monitoring SaaS.

# 13. Security and data boundaries

- All uploads validated by size, extension and content sniffing; streaming upload; randomized storage keys; prevent path traversal and decompression bombs.
- Private file objects; signed short-lived download URLs or proxied authorized downloads; no public bucket.
- Project-scoped authorization at API/service/repository layers; integration tests verify no cross-project access.
- Passwords hashed Argon2; session tokens stored hashed/revocable; cookies Secure/HttpOnly/SameSite; CSRF defense on state changes; TLS outside localhost.
- Rate-limit login, AI runs and upload endpoints. Validate inputs through Pydantic; use ORM parameterization.
- LLM/provider data processing: user consent/approval for data sent externally; **never use actual PureLogics/client documents without written authorization**. Store only allowed data; support deletion/retention plan.
- Importer treats meeting notes and PR content as untrusted; escape HTML and block prompt injection from calling arbitrary APIs.
- GitHub credentials remain server-side with minimum permissions; no token strings in DB plaintext or report exports.
- Audit events for baseline publish, requirement approval, decision, membership and integration changes.
- Backups of DB and object storage for any real deployment. Seeded demonstration can be rebuilt by scripts.
- No public self-registration; initially admin creates users.

# 14. Nonfunctional requirements

| Category | Prototype target | Measurement |
|---|---|---|
| Basic list views | p95 API response under 500 ms at seed data scale | load test / timing |
| Upload | accept <=10MB listed file types; visible stage progress | integration tests |
| Analysis | asynchronous; UI never blocks until LLM finishes | e2e observation |
| Reliability | idempotent replays, visible retries, no duplicate findings | worker tests |
| Provenance | 100% displayed evidence links resolve to stored source spans | automated integrity tests |
| Auth isolation | no project leakage between unshared members | security integration tests |
| Accessibility | keyboard controls, labels, focus visible, contrast checks | manual checklist |
| Deployability | one-command local stack and reproducible seed | new-machine setup run |
| Observability | error code, request/job ID in each failed operation | log inspection |
| Reproducibility | eval run pins dataset, model, prompt and retrieval config | repeat eval script |

These are engineering acceptance targets rather than externally verified production SLAs.

# 15. Tests, evaluation, CI and quality gates

## 15.1 Unit tests

- Requirement version immutability and baseline duplicate-version rejection.
- Change category schema validation, source citation validation and fallback behavior.
- Normalization of CSV input; status mapping, malformed rows and duplicate prevention.
- Retrieval rank fusion and baseline/project isolation.
- Job idempotency, retries and safe error handling.

## 15.2 Integration tests

- Upload → parse → draft requirements → approval → baseline.
- Change input → analysis job → evidence-backed findings.
- Finding decision stored with audit event; old run unchanged after B2 creation.
- Member A cannot see project B or signed document download URL.
- Import same CSV twice creates updates, not duplicate artifacts.
- Storage unavailable; Redis unavailable; provider timeout; parser returns zero text.

## 15.3 End-to-end browser tests

1. Login and create project.
2. Upload synthetic SOW, monitor processing.
3. Review and approve 3 requirements, publish B1.
4. Submit multi-currency note, open proposed finding.
5. Confirm finding with rationale.
6. Import tasks/tests, view traceability.
7. Export report.
8. Log in as read-only reviewer and ensure no mutation allowed.

Playwright is optional but recommended for these critical user paths; screenshot snapshots alone are not acceptance tests.

## 15.4 CI gates

On every push/PR: Python lint/type/test, JS lint/type/test, DB migration smoke, and seeded API integration tests with Postgres/Redis. Run ML benchmark manually or nightly (not every commit if provider calls cost money); CI runs deterministic mock tests of model contracts. Protect main branch only if repository workflow permits.

## 15.5 Done definition

A feature is **done** when it has a working UI/API workflow, input validation, authorized access, error state, DB migration, a test, user-facing empty state, and brief documentation. An AI feature additionally has recorded model/config metadata, grounded evidence, and at least one evaluation case.

# 16. Eight-week sprint plan and dependency order

Assumes approximately 20–25 focused engineering hours/week; reduce scope if real availability is lower. End of each week should produce a runnable milestone, not simply completed tickets.

| Week | Milestone | Backend/DB tasks | Frontend tasks | ML / tests | Exit gate |
|---|---|---|---|---|---|
| 1 | Foundation | repo, compose, migrations, auth, projects, membership | login, shell, projects | synthetic dataset design, architecture ADR | login + create project works |
| 2 | Documents | private storage, parser, spans, jobs, retry | document upload/list/view | parsing fixtures and provenance tests | PDF/DOCX sources visible with anchors |
| 3 | Requirements | extraction schema/service, versions, approvals, baselines | review/edit/approve and publish | requirement-label sample, schema eval | B1 immutable and reproducible |
| 4 | Change analysis | change inputs, analysis runs, retrieval, finding tables | analyze form and results | lexical vs embedding vs hybrid, initial classification | working end-to-end core with citations |
| 5 | Decisions + evidence | review decisions, CSV task/test imports, traceability | detail decisions and traceability | classification/error analysis, labels | reviewers can confirm findings and link artifacts |
| 6 | Hardening + reports | export, job recovery, logs, permission tests | dashboard and reports | held-out eval; confusion matrix | usable product demo from new browser |
| 7 | Optional GitHub + polish | read-only PR sync only if core stable | integration status; evidence UX | benchmark reranker vs baseline; load/security tests | repeatable seeded demo; no critical errors |
| 8 | Final QA + presentation | deployment, backups, README, migrations cleanup | UX/accessibility polish | final frozen benchmark and reproducibility | 7–10 minute end-to-end showcase |

### 16.1 Suggested task sequence (dependency critical path)

`DB + auth → project → document version → source spans → draft requirements → human approval → immutable baseline → change input → async analysis → retrieved evidence → findings → decision → report`.

Only after this chain works, add task/test imports and GitHub. Build one vertical slice through the chain before creating all empty screens.

### 16.2 Kickoff checklist (day 1–3)

- [ ] Create repository with README, branch policy and environment examples.
- [ ] Draft synthetic project documents and hand-label 15 example requests.
- [ ] Sketch DB tables and freeze IDs/state machine.
- [ ] Spin up Postgres/pgvector, Redis, object storage.
- [ ] Create `/health/live`, Alembic baseline migration and login.
- [ ] Record a one-page architecture decision: why dedicated worker, why immutable baselines, why human review.

### 16.3 Weekly review questions

What can be demonstrated end-to-end? What assumption failed? Which measured errors need fixing? Which feature is at risk and can be cut without breaking core user value? Document answers in `docs/decisions.md`.

# 17. Demo dataset and final showcase

## 17.1 Synthetic project fixture: ShopFlow Checkout

Baseline scope draft (publicly shareable fictional project):

- REQ-001: User registers and signs in with email/password.
- REQ-002: Cart shows item prices and subtotal in USD.
- REQ-003: Checkout accepts USD payments only.
- REQ-004: Users receive an order confirmation email.
- REQ-005: Password-reset links expire after 30 minutes.

New meeting note:

> "Please add EUR and GBP checkout, automatic conversion, and location-based prices. We also want refunds from the admin panel. Password resets should remain as agreed."

Imported tasks:

- TASK-12: Implement checkout currency selector — in progress.
- TASK-15: Send order confirmation emails — done.
- TASK-19: Implement admin refunds — backlog.

Imported tests:

- TEST-3: USD checkout total — pass.
- TEST-5: Confirmation email — pass.
- No linked evidence for password reset expiry or currency conversion.

**Expected demo behavior:** extract baseline requirements; detect and cite potential conflict/additions; propose links to TASK-12/19; show missing linked tests; retain human decision; publish downloadable report. This is illustrative fixture data, not product accuracy evidence.

## 17.2 Showcase sequence (7–10 minutes)

1. 0:00–1:00: Explain the cross-document delivery problem and show synthetic SOW.
2. 1:00–2:30: Upload SOW, inspect extracted source-based drafts and publish B1.
3. 2:30–4:30: Submit conflicting meeting note; inspect finding citations and human decision.
4. 4:30–6:00: Import tasks/test CSV and show suggested vs accepted links.
5. 6:00–7:00: Show evidence gap, export project report.
6. 7:00–9:00: Show architecture, failure handling and actual offline evaluation results.
7. 9:00–10:00: Name known limitations and next engineering steps; invite technical questions.

## 17.3 Final deliverables to manager

- Deployed or reproducibly runnable web app.
- Source code with clean repo structure and database migrations.
- Synthetic demo dataset and seed script.
- Architecture diagram + short decisions log.
- API documentation generated by FastAPI/OpenAPI.
- Evaluation dataset rubric, metrics and error breakdown.
- Automated unit/integration/permission tests.
- Deployment instructions, environment sample and brief walkthrough video (optional).

# 18. Risks, trade-offs and mitigations

| Risk | Likelihood / consequence | Mitigation |
|---|---|---|
| Text extraction misreads PDF layout | Common; wrong source spans | Support selectable-text only, inspect spans, cite precise page; flag uncertain output. |
| LLM invents source text or classifications | Material trust risk | structured output, citation validation, ambiguity class, reviewer gate. |
| Too many features in 8 weeks | Very high scope risk | prioritize critical chain; defer GitHub, visual polish, notifications. |
| Small / biased evaluation data | Weak model evidence | split by project; include negatives; reviewer rubric; disclose N. |
| New requirements misclassified due to retrieval miss | False scope alerts | hybrid retrieval, top-k review, insufficient-evidence fallback. |
| Testing evidence missing | False claim of incomplete delivery | label only recorded-evidence gap; allow manual attachments. |
| External LLM provider unavailable | App stuck | retries, visible status, fixture-mode demo, configurable provider. |
| Private source material leaked to provider | Severe | synthetic/approved data, clear policy, no raw logs, protected secrets. |
| GitHub API permissions/rate limits | P1 delayed | CSV source guaranteed; incremental pagination, least privileges. |
| Concurrent edits / stale review | Lost decisions | optimistic concurrency, append-only decisions, clear stale warning. |
| Running all services on free serverless hosting | Worker unreliable | separate persistent/container worker; local Docker fallback. |

# 19. Acceptance checklist / release gates

**Core workflow**

- [ ] New user with authorized access can create a project.
- [ ] Uploaded text-based documents parse asynchronously; citation spans are accessible.
- [ ] AI-extracted candidates require user review, edit and approval.
- [ ] Baselines preserve exact approved versions and remain immutable.
- [ ] New client request compares against a **selected** baseline, not latest drafts.
- [ ] Findings include traceable evidence and clear non-legal classification wording.
- [ ] Reviewer can confirm/dismiss/request clarification; decision has audit history.
- [ ] Task and test CSV imports work; proposed links are distinguishable from accepted links.
- [ ] Requirements without linked tests are reported as **evidence gaps**, not implementation failures.
- [ ] User exports reproducible report with baseline/run identifiers.

**Technical and AI quality**

- [ ] Failed jobs are visible, retryable and idempotent.
- [ ] Non-members cannot retrieve another project's records or original files.
- [ ] Model calls are provider-adapted, timed out, and safely logged.
- [ ] A held-out benchmark compares at least a simple baseline and improved pipeline.
- [ ] Evaluation run records labels, metrics, config, failures, sample sizes and limitations.
- [ ] CI, migrations, seed and Docker startup all work on a fresh checkout.
- [ ] No production secrets or real client documents ship in the repository.
- [ ] Known limitations are documented and surfaced in the presentation.

# 20. First engineering decisions to freeze

| ADR | Proposed decision | Why |
|---|---|---|
| ADR-001 | Single workspace with project-scoped access | enough security structure, no tenant complexity |
| ADR-002 | Immutable requirement versions and baselines | analyses must be historically reproducible |
| ADR-003 | AI outputs proposed findings only | scope decisions require human authority |
| ADR-004 | FastAPI owns domain/API; Next.js owns UI | one source of business truth |
| ADR-005 | PostgreSQL + pgvector, not separate vector DB | simpler reliable joins and provenance |
| ADR-006 | Redis+RQ worker separated from request process | long tasks and retries |
| ADR-007 | CSV first, GitHub read-only second | guaranteed demo even without API credentials |
| ADR-008 | No scanned-PDF OCR in MVP | avoid wrong extracted evidence and scope expansion |
| ADR-009 | Synthetic public demo and labeled benchmark | protect data and allow reproducibility |
| ADR-010 | Server-side LLM credentials and provider adapter | security and portability |

# 21. Official technical references

- FastAPI background-task caveat and dedicated workers: https://fastapi.tiangolo.com/tutorial/background-tasks/
- FastAPI authentication patterns: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- Next.js App Router server/client split: https://nextjs.org/docs/app/getting-started/server-and-client-components
- Next.js data fetching/cache: https://nextjs.org/docs/app/getting-started/fetching-data
- SQLAlchemy asynchronous ORM: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- PostgreSQL pgvector and hybrid search: https://github.com/pgvector/pgvector
- Sentence Transformers cross-encoders: https://www.sbert.net/docs/cross_encoder/usage/usage.html
- GitHub Pull Requests REST API: https://docs.github.com/en/rest/pulls/pulls
- GitHub webhook signature verification (for future): https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries

---

## Final project success statement

**DeliveryGap AI is successful if a reviewer can take a real-looking software scope document and later meeting note, see accurate and source-grounded potential delivery changes, inspect related task/test evidence, record a human decision, export an auditable report, and reproduce the ML evaluations behind the analysis.**

The priority is an honest, dependable engineering workflow — not the number of AI features or visual effects.
