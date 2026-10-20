# Initial synthetic evaluation fixtures

The [ShopFlow scope](../datasets/synthetic_project/scope.md) and
[meeting note](../datasets/synthetic_project/meeting-notes.md) reproduce the fictional
PRD example. The [versioned case file](../datasets/eval/shopflow-v1.json) contains
15 development requests: four in-scope, three conflicts, three potential additions,
two ambiguous requests, and three insufficient-evidence cases.

All labels are agent-authored proposals **awaiting human review**. They do not yet
satisfy the plan's hand-labeling gate. There are no model predictions, accuracy
metrics, or claims of human approval in this dataset.

## Review rubric

- `IN_SCOPE`: the cited requirement entails the requested behavior.
- `CONFLICT`: quote an explicit condition incompatible with the request. Absence is insufficient.
- `POTENTIAL_SCOPE_ADDITION`: identify a concrete extension to supplied scope, preserve
  the caveat that other agreement provisions may cover it, and require human review.
- `AMBIGUOUS`: the request lacks enough specificity to determine the desired behavior.
- `INSUFFICIENT_EVIDENCE`: required evidence is unavailable or does not support a comparison.
  Topic overlap does not establish evidentiary support.

The two ambiguous and three insufficient-evidence cases comprise 5/15 difficult
cases (33%). This is a design choice, not a measured difficulty estimate. In particular,
SF-015 has a relevant checkout requirement but no gold supporting tax-policy citation.
Missing evidence never establishes missing implementation.

Review each input, label, rationale, and exact source quote. Record reviewer identity,
date, disagreements, and adjudication before promoting a new dataset version to
human-reviewed status. Keep this version immutable once used for an experiment.

## Structural validation and live evaluation

Run `node scripts/validate-evaluation-fixtures.mjs` from the repository root, or
`pnpm fixtures:validate`. CI runs this structural check. It checks unique identities,
the five-class vocabulary, baseline membership, exact source anchors, reference
integrity, and required evidence for supported conclusions. It does not assess semantic label correctness or execute a classifier.

Span IDs are fixture-local anchors, not database IDs or parser output. Quotes resolve
against the UTF-8 Markdown source. Phase 1 must produce its own canonical offsets;
later fixture ingestion must map these anchors to authorized persisted source spans.
No baseline has been published in the application by adding these files.

All ShopFlow cases and future paraphrases belong to one `shopflow-checkout` family
and the development split. Do not randomly split this family into train/test data.
Grow separate fictional project families toward 100–150 human-reviewed cases and
freeze held-out families before tuning. Store dataset/config hashes and actual
per-case predictions before reporting metrics. Fixture workflow success is not
evidence of live-model quality.

## Hybrid runtime and evaluation runner

Queued change analysis now combines BM25 token ranking and exact cosine similarity over
cached 1024-dimension Neon Gateway embeddings, then fuses rankings with reciprocal-rank
fusion. Results persist the top-five candidate ranks/scores, exact input and baseline
quotes, a frozen configuration hash, and a warning that retrieval scores are not confidence.
Provider findings remain proposals; project-lead consent is required before extraction or
analysis sends material to the configured external provider.

The optional evaluation runner sends only this synthetic development fixture when explicitly
authorized:

```powershell
& '.venv\Scripts\python.exe' scripts\evaluate_hybrid_analysis.py --send-synthetic-data
```

The script writes a per-case prediction artifact with dataset/config hashes, candidate ranks,
citation-validation outcomes, and provisional candidate coverage against the proposed
references. Since all labels remain `pending_human_review`, it deliberately withholds
label-agreement and model-quality metrics. It does not execute in CI and must not be run
against real project material. Supply Neon Gateway credentials through the configured
environment; no credentials belong in the repository.

The default embedding configuration is `qwen3-embedding-0-6b` at 1024 dimensions.
The gateway model and live provider path have not passed acceptance: the configured
organization's Free plan previously blocked live calls. Browser/API tests inject synthetic
providers and prove wiring, citation safety, consent checks, cancellation, and persistence;
they do not prove live-model quality. Human review and held-out project families remain
required before reporting classification quality.
