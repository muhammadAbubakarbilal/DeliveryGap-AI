"""Run the existing tests in disposable schemas on the configured Neon database."""

import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps/api"))
import pytest  # noqa: E402
from app.config import get_settings  # noqa: E402

settings = get_settings()
os.environ["TEST_DATABASE_URL"] = settings.database_url_unpooled or settings.database_url
os.chdir(root)
raise SystemExit(pytest.main(sys.argv[1:] or ["-q"]))
