---
name: fastapi-architect
description: Design and implement DeliveryGap AI FastAPI endpoints, services, schemas, validation, and authorization boundaries.
---

## Activate when

Creating or modifying an endpoint, domain service, request/response contract, validation rule, or authorization-sensitive operation.

## Responsibilities

- Keep routes thin and domain behavior authoritative in services/repositories.
- Use Pydantic v2, explicit transactions, consistent errors, pagination, and request IDs.
- Enforce project-scoped roles on every read and mutation.

## Procedure

1. Define the contract, actor matrix, idempotency/concurrency behavior, and transaction boundary.
2. Inspect existing dependencies, schemas, services, and error handling.
3. Implement validation, authorization, persistence orchestration, and safe errors.
4. Update OpenAPI and generated frontend types when the contract changes.

## Required checks

- Unit and API tests for success, invalid input, forbidden access, guessed IDs, conflicts, and retries.
- No sensitive values in errors or logs.
- OpenAPI export is deterministic and synchronized.

## Completion criteria

The endpoint has a documented contract, server-enforced authorization, transactionally correct behavior, tests, and synchronized client types.
