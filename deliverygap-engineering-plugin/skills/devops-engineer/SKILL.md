---
name: devops-engineer
description: Build reproducible DeliveryGap AI environments, Compose services, CI, migrations, secrets, health checks, and release procedures.
---

## Activate when

Setting up the repository, containers, service dependencies, CI/CD, environment variables, monitoring, backups, or deployment.

## Responsibilities

- Keep local and CI environments reproducible and secrets outside source control.
- Configure health/readiness checks, migration ordering, private storage, worker operation, and recovery documentation.
- Keep Windows host constraints explicit while running Linux-native dependencies in containers.

## Procedure

1. Inspect current locks, Dockerfiles, Compose, CI, env example, and task definitions.
2. Add pinned, minimal configuration with health dependencies and explicit migration tasks.
3. Verify clean setup, migration upgrade/downgrade, seed rerun, health behavior, and failure recovery.
4. Document startup, smoke, backup/restore, and environment prerequisites.

## Required checks

- No secrets in source or logs.
- Services have bounded health/readiness behavior and persistent data where needed.
- CI runs lint, types, tests, migrations, contract generation, build, and browser smoke when available.

## Completion criteria

A fresh environment can be started and verified reproducibly, or all unavailable infrastructure is precisely documented with an approved alternative.
