---
name: ai-rag-engineer
description: Build grounded requirement extraction, retrieval, classification, citation validation, and evaluation for DeliveryGap AI.
---

## Activate when

Implementing embeddings, retrieval, extraction, change analysis, model adapters, structured outputs, citations, or ML evaluation.

## Responsibilities

- Retrieve only approved requirement versions in the selected baseline/project.
- Preserve provenance, validate citations, abstain on insufficient evidence, and keep human decisions authoritative.
- Measure quality without treating retrieval scores as confidence probabilities.

## Procedure

1. Freeze input, baseline, provider/model, prompt, retrieval settings, and config hash.
2. Bound chunks, requests, tokens, provider calls, and timeouts.
3. Validate structured output, source membership, quote alignment, evidence side, and baseline membership.
4. Persist deterministic diagnostics and partial results idempotently.
5. Compare retrieval/classification behavior on frozen synthetic evaluation cases.

## Required checks

- Invalid citations downgrade safely and never fabricate evidence.
- Fixture mode is labeled and rejects unknown fixtures.
- Prompt inputs are untrusted; raw documents/provider responses are not logged.

## Completion criteria

The pipeline produces reproducible, grounded, bounded results with visible warnings, persisted diagnostics, and measured limitations.
