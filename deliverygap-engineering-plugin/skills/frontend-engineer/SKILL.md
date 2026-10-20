---
name: frontend-engineer
description: Implement strict TypeScript Next.js App Router UI and API integration for DeliveryGap AI.
---

## Activate when

Implementing pages, components, forms, tables, uploads, filters, polling, mutations, or frontend/API integration.

## Responsibilities

- Keep FastAPI authoritative and use generated OpenAPI types.
- Implement accessible, resilient loading, empty, permission, validation, and failure states.
- Keep client JavaScript focused and state boundaries clear.

## Procedure

1. Inspect the route, shell, API wrapper, generated types, and existing components.
2. Confirm the UX and design-system contract before coding.
3. Implement server rendering where appropriate and client interaction only where required.
4. Handle aborts, stale navigation, session expiry, optimistic concurrency, and mutation errors.
5. Verify the real rendered route at responsive sizes.

## Required checks

- `tsc --noEmit`, ESLint, production build, and focused Playwright/component coverage.
- Keyboard navigation, labels, focus, and reduced-motion behavior.
- No domain logic or security decision duplicated in Next.js.

## Completion criteria

The route is integrated with the API, all relevant states work, accessibility checks pass, and automated/static verification is recorded.
