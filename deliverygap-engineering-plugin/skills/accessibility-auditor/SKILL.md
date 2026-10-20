---
name: accessibility-auditor
description: Audit DeliveryGap AI interfaces for semantic, keyboard, focus, form, contrast, motion, and WCAG 2.2 AA issues.
---

## Activate when

Creating or modifying interactive UI, forms, dialogs, tables, navigation, review panels, or preparing a release.

## Responsibilities

- Verify semantic structure, accessible names, focus management, announcements, contrast, and keyboard operation.
- Check loading, error, validation, permission, and reduced-motion states.
- Report concrete evidence and severity rather than generic compliance claims.

## Procedure

1. Inspect the route at desktop and narrow viewport sizes.
2. Navigate with keyboard only and test focus order, traps, escape behavior, and visible focus.
3. Inspect labels, headings, table semantics, live regions, contrast, and motion preferences.
4. Add or update focused browser/accessibility tests for regressions.

## Required checks

- Every interactive control has an accessible name and usable keyboard path.
- Errors and async state changes are perceivable without color alone.
- No critical focus, contrast, overflow, or reduced-motion issue remains.

## Completion criteria

Findings are fixed or explicitly accepted with rationale, and the tested route has evidence for the relevant WCAG behaviors.
