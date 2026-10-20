---
name: postgres-data-architect
description: Design DeliveryGap AI PostgreSQL schemas, Alembic migrations, constraints, and concurrency-safe persistence.
---

## Activate when

Adding entities, migrations, versioning, baselines, audit history, relationships, indexes, or transaction behavior.

## Responsibilities

- Preserve referential integrity, project isolation, immutable history, and append-only decisions.
- Use PostgreSQL/pgvector semantics rather than relying on SQLite behavior.
- Make concurrency and idempotency explicit in schema and service design.

## Procedure

1. Model ownership, composite scope, lifecycle, revision, and deletion/archival rules.
2. Add reversible Alembic migrations with constraints and indexes.
3. Add repository/service transaction boundaries and expected-revision checks.
4. Test clean upgrade, downgrade, concurrent conflicts, and cross-project references.

## Required checks

- Real PostgreSQL migration/integration checks where available.
- Constraints reject invalid project references and illegal state transitions.
- Historical records remain immutable and query paths are bounded.

## Completion criteria

The schema, migration, persistence code, and tests enforce the domain invariants under normal and concurrent operations.
