---
name: deliverygap-orchestrator
description: Coordinate DeliveryGap AI feature work across product, UX, backend, data, AI, security, QA, performance, and release skills.
---

# DeliveryGap engineering orchestrator

## Activate when

Use for a new feature or phase, cross-layer work, milestone planning, architecture tradeoffs, or release readiness. Do not use it for a narrowly scoped single-file edit unless coordination is needed.

## Responsibilities

- Treat the PRD and implementation plan as authoritative.
- Select the smallest primary and supporting skills from the matrix below.
- Preserve project isolation, provenance, immutable baselines, human decisions, and P0 boundaries.
- Define a complete vertical slice before implementation.

## Procedure

1. Inspect the relevant PRD/plan sections, repository structure, current tests, and existing patterns.
2. Record scope, actors, permissions, dependencies, acceptance criteria, risks, and the implementation sequence.
3. Activate product/UX/design review for user-facing work, then the applicable technical skills.
4. Implement API, data, UI, jobs, and documentation as one coherent slice.
5. Run security, QA, accessibility, and performance checks proportional to risk.
6. Report passed checks, unavailable infrastructure, remaining gaps, and the exact next task.

## Required checks

- Relevant unit/integration/browser tests and static checks.
- Authorization and project-isolation coverage.
- Loading, empty, error, permission, and retry states.
- API/OpenAPI and migration consistency where applicable.
- No fabricated completion claims.

## Completion criteria

The slice satisfies its acceptance criteria, is integrated across affected layers, has documented decisions, and has an evidence-backed verification report. Blocked criteria remain explicitly incomplete.
