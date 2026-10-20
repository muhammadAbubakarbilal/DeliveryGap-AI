---
name: motion-interactions
description: Add purposeful, accessible motion to DeliveryGap AI interactions and processing feedback.
---

## Activate when

Adding transitions, drawers, dialogs, menus, expanding evidence, upload progress, polling feedback, or perceived-performance improvements.

## Responsibilities

- Use subtle motion to clarify state and spatial relationships.
- Respect reduced-motion preferences and avoid disrupting evidence review.
- Prevent layout shifts and unnecessary rendering cost.

## Procedure

1. Define the state change and why motion improves comprehension.
2. Reuse existing timing/easing tokens or create the smallest justified token.
3. Implement enter/exit/focus behavior with reduced-motion fallback.
4. Test interrupted, slow, failed, and keyboard-triggered transitions.

## Required checks

- Reduced-motion media behavior is verified.
- Motion does not hide content, trap focus, or create layout shift.
- Performance remains acceptable on the target viewport.

## Completion criteria

Motion is purposeful, optional for users who request reduced motion, and verified in normal and interrupted interaction paths.
