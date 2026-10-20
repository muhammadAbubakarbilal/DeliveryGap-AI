"""Run from repository root: uv run python scripts/export_openapi.py."""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps" / "api"))
from app.main import app  # noqa: E402

target = root / "docs" / "openapi.json"
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"Exported {len(app.openapi()['paths'])} API paths.")
