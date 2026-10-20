"""Run the optional live-provider evaluation on synthetic development data only."""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "apps" / "api"))
    from app.ai_gateway import GatewayUnavailable
    from app.config import get_settings
    from app.evaluation import evaluate_fixture
    from app.grounded_analysis import embed_provider, extract_provider

    fixture = root / "datasets" / "eval" / "shopflow-v1.json"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--send-synthetic-data",
        action="store_true",
        help="Confirm the synthetic fixture may be sent to the configured external provider.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "artifacts" / "evaluation" / "shopflow-v1-predictions.json",
    )
    args = parser.parse_args()
    if not args.send_synthetic_data:
        parser.error("pass --send-synthetic-data to authorize external processing of this fixture")
    settings = get_settings()
    try:
        report = evaluate_fixture(
            fixture,
            embed_provider,
            extract_provider,
            settings.neon_embedding_model,
            "gpt-5-mini",
        )
    except GatewayUnavailable as exc:
        print(str(exc), file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(report['cases'])} predictions to {args.output}")
    print(
        "Human review is pending; label-agreement and quality metrics are intentionally withheld."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
