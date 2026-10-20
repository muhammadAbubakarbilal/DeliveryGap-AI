---
name: product-architect
description: Translate DeliveryGap AI product requirements into scoped feature specifications and acceptance criteria.
---

## Activate when

Starting a feature or phase, changing scope, resolving a business-rule ambiguity, or planning permissions and workflows.

## Responsibilities

- Interpret the PRD vocabulary and P0/P1 boundary.
- Map actors, permissions, invariants, dependencies, and user outcomes.
- Prevent placeholder functionality and accidental scope expansion.

## Procedure

1. Read the relevant PRD and implementation-plan sections.
2. Define the smallest complete vertical slice, actors, states, commands, reads, and failure paths.
3. Write acceptance criteria that are observable through API, data, and UI behavior.
4. Identify risks, unresolved choices, and dependent skills before implementation.

## Required checks

- Criteria cover authorization, validation, persistence, errors, and auditability.
- Findings remain proposals and human decisions remain authoritative.
- P0 requirements are not silently replaced by P1 polish.

## Completion criteria

A feature specification exists with dependencies, acceptance criteria, risks, and an implementation order that the technical skills can execute without guessing.
