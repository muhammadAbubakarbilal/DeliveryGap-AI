---
name: document-processing-engineer
description: Implement bounded private document ingestion, parsing, canonical source spans, and citation resolution for DeliveryGap AI.
---

## Activate when

Adding PDF, DOCX, TXT, Markdown, upload, parsing, source-viewing, document-version, or citation-location behavior.

## Responsibilities

- Preserve immutable originals, canonical extracted text, exact source spans, and parse warnings.
- Distinguish selectable text from unsupported/scanned input; do not claim OCR without implementation.
- Keep source access project-authorized and private.

## Procedure

1. Validate extension, content, size, decompressed limits, and private storage destination.
2. Parse into canonical page/paragraph/line spans with half-open Unicode offsets.
3. Persist version, spans, chunks, warnings, and status transitions transactionally.
4. Expose authorized source/download resolution and recoverable retry/manual-text paths.

## Required checks

- Supported-format fixtures resolve expected anchors.
- Oversize, malformed, scanned, and unauthorized inputs fail safely.
- Originals are immutable and raw text is absent from logs.

## Completion criteria

Each supported input has deterministic provenance and authorized viewing, with explicit failure/manual-input behavior and tests.
