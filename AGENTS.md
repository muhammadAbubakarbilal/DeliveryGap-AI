# DeliveryGap AI engineering standards

## Source of truth

Product scope, business rules, API coverage, data invariants, and delivery gates are defined by `DeliveryGap_AI_Complete_PRD.md` and `IMPLEMENTATION_PLAN.md`. Preserve the PRD vocabulary: findings are proposals, missing evidence is not proof of missing implementation, and retrieval scores are not confidence probabilities.

## Current delivery stage

Phase 0 (foundation) is implemented in the repository. The next work item is Phase 1 document sources. Do not build later screens as disconnected placeholders; complete vertical slices with API, persistence, authorization, failure states, and tests.

## Architecture rules

- `apps/api` is the authoritative domain layer. Keep routes, schemas, persistence, and services separated as new features are added.
- Use FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL/pgvector, Redis/RQ, and private S3-compatible storage as specified in the plan.
- Keep long-running parsing, embedding, model, import, and report work out of ordinary web requests.
- Use project-scoped authorization on every read and mutation; UI gating never replaces server checks.
- Preserve immutable document originals, source provenance, requirement revisions, published baselines, append-only decisions, artifact history, and report snapshots.
- Use idempotency keys for retryable commands and explicit optimistic-concurrency checks for reviewer decisions.
- Do not log passwords, cookies, secrets, raw source text, or raw provider responses.

## Frontend rules

- Use Next.js App Router with strict TypeScript and the generated OpenAPI types.
- Keep backend behavior in FastAPI; Next.js is a UI and proxy layer, not a second domain backend.
- Every interactive workflow needs loading, empty, validation, permission, failure, and expired-session behavior where applicable.
- Use semantic controls, visible focus, keyboard support, accessible labels/errors, and reduced-motion-safe interactions.

## Skill routing

The repository's reusable instructions are maintained in [deliverygap-engineering-plugin](./deliverygap-engineering-plugin/). Supported repository entrypoints in [.agents/skills](./.agents/skills/) load those instructions. Codex CLI runtime discovery of all 16 entrypoints is verified; see [engineering-skills.md](./docs/engineering-skills.md) for evidence and invocation. Use `/skills` or `$skill-name`; read the entrypoint and its linked canonical instructions before acting. No global installation is required.

Use the smallest relevant specialist workflow for each change:

| Work | Primary | Supporting |
| --- | --- | --- |
| New feature or phase | product architect | relevant domain specialist, QA |
| API or business rule | FastAPI architect | security, PostgreSQL, QA |
| Schema or migration | PostgreSQL data architect | FastAPI, QA |
| Upload/parsing/jobs | document processing engineer | background jobs, security, frontend, QA |
| AI/retrieval | AI/RAG engineer | document processing, jobs, QA |
| UI workflow | SaaS UX architect | frontend, design system, accessibility |
| Release/deployment | DevOps engineer | security, QA, performance |

Do not modify the host-managed global skill catalog. Keep the plugin instructions authoritative and the repository entrypoint names/descriptions synchronized. Marketplace installation is optional distribution, separate from verified repository discovery.

## Phase routing

| Phase | Primary skills | Supporting skills |
| --- | --- | --- |
| 0 Foundation | deliverygap-orchestrator, product-architect, fastapi-architect, postgres-data-architect | security-engineer, devops-engineer, frontend-engineer, qa-testing-engineer |
| 1 Document sources | document-processing-engineer, background-jobs-engineer | postgres-data-architect, security-engineer, frontend-engineer, qa-testing-engineer |
| 2 Approved scope | ai-rag-engineer, product-architect, postgres-data-architect | saas-ux-architect, frontend-engineer, qa-testing-engineer |
| 3 Change analysis | ai-rag-engineer, background-jobs-engineer | postgres-data-architect, saas-ux-architect, frontend-engineer, security-engineer, qa-testing-engineer |
| 4 Delivery evidence | fastapi-architect, postgres-data-architect, product-architect | frontend-engineer, security-engineer, qa-testing-engineer |
| 5 Reliability/reporting | qa-testing-engineer, security-engineer, performance-engineer | fastapi-architect, postgres-data-architect, ai-rag-engineer |
| 6 Stabilization | performance-engineer, accessibility-auditor, design-system-engineer | frontend-engineer, qa-testing-engineer, motion-interactions |
| 7 Release | devops-engineer, security-engineer, qa-testing-engineer | performance-engineer, accessibility-auditor |

## Verification

Before calling a feature complete, run the narrowest relevant checks plus the full applicable suite. Backend unit tests alone do not prove PostgreSQL constraints, queue recovery, browser behavior, or project isolation. Report unavailable infrastructure (for example Docker/PostgreSQL) explicitly instead of claiming it passed.

Typical local checks:

```powershell
& '.venv/Scripts/python.exe' -m pytest
pnpm.cmd --filter @deliverygap/web typecheck
pnpm.cmd --filter @deliverygap/web lint
pnpm.cmd --filter @deliverygap/web build
```
