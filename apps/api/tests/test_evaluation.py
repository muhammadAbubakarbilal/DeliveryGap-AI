import json
from pathlib import Path

from app.evaluation import evaluate_fixture

FIXTURE = Path(__file__).resolve().parents[3] / "datasets" / "eval" / "shopflow-v1.json"


def fake_embeddings(inputs):
    return [[1.0, *([0.0] * 1023)] for _ in inputs]


def fake_completion(prompt):
    data = json.loads(prompt[prompt.index('{"request":') :])
    return json.dumps(
        {
            "findings": [
                {
                    "classification": "AMBIGUOUS",
                    "summary": "Synthetic test prediction.",
                    "input_quote": data["request"],
                    "requirement_version_id": None,
                    "evidence_quote": None,
                }
            ]
        }
    )


def test_evaluation_writes_per_case_predictions_without_claiming_quality():
    report = evaluate_fixture(
        FIXTURE,
        fake_embeddings,
        fake_completion,
        "synthetic-test-embedding",
        "synthetic-test-completion",
    )
    assert report["dataset"]["review_status"] == "pending_human_review"
    assert report["label_agreement"] is None
    assert report["label_agreement_status"] == "withheld_pending_human_review"
    assert report["citation_validation"] == {"valid": 15, "cases_with_prediction": 15}
    assert len(report["cases"]) == 15
    assert report["cases"][0]["predicted_classification"] == "AMBIGUOUS"
    assert report["provisional_candidate_coverage_at_5"]["eligible_cases"] == 12


def test_evaluation_downgrades_invalid_model_citations():
    def invalid_completion(prompt):
        data = json.loads(prompt[prompt.index('{"request":') :])
        requirement = data["evidence"][0]["id"]
        return json.dumps(
            {
                "findings": [
                    {
                        "classification": "CONFLICT",
                        "summary": "Invalid citation.",
                        "input_quote": data["request"],
                        "requirement_version_id": requirement,
                        "evidence_quote": "not in the supplied source",
                    }
                ]
            }
        )

    report = evaluate_fixture(
        FIXTURE,
        fake_embeddings,
        invalid_completion,
        "synthetic-test-embedding",
        "synthetic-test-completion",
    )
    assert report["citation_validation"] == {"valid": 0, "cases_with_prediction": 15}
    assert all(
        case["predicted_classification"] == "INSUFFICIENT_EVIDENCE" for case in report["cases"]
    )
