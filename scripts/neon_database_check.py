"""Read-only connectivity and schema inventory; never prints connection credentials."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))

from app.config import get_settings  # noqa: E402
from sqlalchemy import create_engine, inspect, text  # noqa: E402

settings = get_settings()
try:
    engine = create_engine(settings.database_url_unpooled or settings.database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1
        print("Postgres: SELECT 1 passed")
        print("Public tables:", ", ".join(inspect(connection).get_table_names(schema="public")))
    engine.dispose()
except Exception as exc:
    print("Postgres check failed:", type(exc).__name__)
    raise SystemExit(1) from None
