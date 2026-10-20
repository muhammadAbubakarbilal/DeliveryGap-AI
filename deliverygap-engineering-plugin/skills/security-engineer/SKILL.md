---
name: security-engineer
description: Review and harden DeliveryGap AI authentication, authorization, uploads, secrets, external providers, and trust boundaries.
---

## Activate when

Changing sessions, roles, project membership, private files, uploads, provider calls, admin actions, or deployment configuration.

## Responsibilities

- Enforce server-side role/project isolation and safe session/CSRF behavior.
- Protect private storage, secrets, logs, and external data transfers.
- Identify prompt injection, confused-deputy, enumeration, and unsafe retry risks.

## Procedure

1. Map actors, assets, trust boundaries, attacker inputs, and authorization decisions.
2. Review routes, queries, storage keys, jobs, logs, errors, and frontend exposure.
3. Add validation, least privilege, origin/CSRF/session controls, and safe failure behavior.
4. Test forbidden reads/writes, guessed IDs, revoked sessions, cross-project access, and unsafe inputs.

## Required checks

- No sensitive data in errors/logs/client persistence.
- Every project-scoped operation rechecks membership, including queued work.
- Uploads and external processing have bounded limits and explicit authorization.

## Completion criteria

Threats are addressed or documented with residual risk, and security-focused tests demonstrate isolation and safe failure.
