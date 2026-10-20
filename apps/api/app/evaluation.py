"""Build a reproducible per-case artifact for the synthetic development fixture."""

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from app.ai_gateway import GatewayUnavailable
from app.grounded_analysis import (
    EMBEDDING_DIMENSIONS,
    PROMPT,
    QUERY_INSTRUCTION,
    RETRIEVAL_TOP_K,
    EmbeddingProvider,
    Output,
    embed_bounded,
    fuse_candidates,
    validate_citations,
)
from app.models import now

CompletionProvider = Callable[[str], str]


def evaluate_fixture(
    fixture_path: Path,
    embedder: EmbeddingProvider,
    completion: CompletionProvider,
    embedding_model: str,
    completion_model: str,
) -> dict[str, object]:
    raw_fixture = fixture_path.read_bytes()
    fixture = json.loads(raw_fixture)
    requirements = cast(list[dict[str, str]], fixture["requirements"])
    cases = cast(list[dict[str, object]], fixture["cases"])
    documents = [
        {
            "id": requirement["code"],
            "code": requirement["code"],
            "title": requirement["code"],
            "content": requirement["quote"],
            "source_quote": requirement["quote"],
            "source_span_id": requirement["span_id"],
            "text": requirement["quote"],
        }
        for requirement in requirements
    ]
    document_vectors = embed_bounded(
        [
            f"{document['title']}\n{document['content']}\n{document['source_quote']}"
            for document in documents
        ],
        embedder,
    )
    embeddings = {
        document["id"]: vector for document, vector in zip(documents, document_vectors, strict=True)
    }
    predictions = []
    class_counts: Counter[str] = Counter()
    candidate_coverage = 0
    candidate_eligible = 0
    citation_valid_count = 0
    cases_with_prediction = 0

    for case in cases:
        request_text = str(case["input_text"])
        candidates: list[dict[str, object]] = []
        prediction: dict[str, object] = {
            "case_id": case["id"],
            "proposed_label": case["expected_class"],
            "predicted_classification": None,
            "citation_valid": None,
            "input_quote": None,
            "requirement_version_id": None,
            "evidence_quote": None,
            "retrieval_candidates": [],
        }
        try:
            candidates = fuse_candidates(
                documents,
                request_text,
                embed_bounded([QUERY_INSTRUCTION + request_text], embedder)[0],
                embeddings,
            )
            prediction["retrieval_candidates"] = [
                {
                    "requirement_code": candidate["code"],
                    "source_span_id": candidate["source_span_id"],
                    "lexical_rank": candidate["lexical_rank"],
                    "bm25_score": candidate["bm25_score"],
                    "semantic_rank": candidate["semantic_rank"],
                    "cosine_similarity": candidate["cosine_similarity"],
                    "fused_rank": candidate["fused_rank"],
                    "rrf_score": candidate["rrf_score"],
                }
                for candidate in candidates
            ]
            prompt_evidence = [
                {
                    key: candidate[key]
                    for key in ("id", "title", "content", "source_quote", "source_span_id")
                }
                for candidate in candidates
            ]
            prompt = PROMPT + json.dumps(
                {"request": request_text, "evidence": prompt_evidence}, ensure_ascii=False
            )
            raw_output = completion(prompt)
            if len(raw_output) > 50000:
                raise ValueError("Provider output exceeds the configured limit")
            proposals = Output.model_validate_json(raw_output).findings
            proposal = proposals[0]
            valid, input_cited, cited = validate_citations(proposal, request_text, candidates)
            predicted = proposal.classification if valid else "INSUFFICIENT_EVIDENCE"
            prediction.update(
                {
                    "predicted_classification": predicted,
                    "citation_valid": valid,
                    "input_quote": proposal.input_quote if input_cited else None,
                    "requirement_version_id": (
                        proposal.requirement_version_id if valid and cited else None
                    ),
                    "evidence_quote": proposal.evidence_quote if valid and cited else None,
                }
            )
            class_counts[predicted] += 1
            cases_with_prediction += 1
            citation_valid_count += int(valid)
        except GatewayUnavailable as exc:
            prediction["error"] = str(exc)
        except ValidationError:
            prediction["error"] = (
                "Provider output failed schema or citation validation; no prediction saved"
            )
        except ValueError:
            prediction["error"] = (
                "Embedding output was invalid or provider output exceeded limits; "
                "no prediction saved"
            )

        gold_span_ids = cast(list[str], case["gold_evidence_span_ids"])
        if gold_span_ids:
            candidate_eligible += 1
            retrieved_spans = {
                str(candidate["source_span_id"]) for candidate in candidates[:RETRIEVAL_TOP_K]
            }
            candidate_coverage += int(bool(retrieved_spans.intersection(gold_span_ids)))
        predictions.append(prediction)

    config = {
        "retrieval_method": "bm25+qwen3-embedding-rrf-v1",
        "embedding_model": embedding_model,
        "embedding_dimensions": EMBEDDING_DIMENSIONS,
        "completion_model": completion_model,
        "retrieval_top_k": RETRIEVAL_TOP_K,
        "prompt_version": "analysis-v1",
    }
    return {
        "schema_version": 1,
        "dataset": {
            "version": fixture["dataset_version"],
            "sha256": hashlib.sha256(raw_fixture).hexdigest(),
            "family_id": fixture["family_id"],
            "split": fixture["split"],
            "review_status": fixture["review_status"],
            "synthetic": fixture["synthetic"],
        },
        "config": config,
        "config_sha256": hashlib.sha256(
            json.dumps(config, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "generated_at": now().isoformat(),
        "label_agreement": None,
        "label_agreement_status": "withheld_pending_human_review",
        "provisional_candidate_coverage_at_5": {
            "hits": candidate_coverage,
            "eligible_cases": candidate_eligible,
            "ratio": (candidate_coverage / candidate_eligible if candidate_eligible else None),
            "interpretation": "Coverage against agent-proposed references, not ground truth.",
        },
        "predicted_class_counts": dict(sorted(class_counts.items())),
        "citation_validation": {
            "valid": citation_valid_count,
            "cases_with_prediction": cases_with_prediction,
        },
        "warning": (
            "Synthetic development predictions only. Labels await human review; "
            "no accuracy or model-quality claim is reported. Retrieval scores are not confidence."
        ),
        "cases": predictions,
    }
