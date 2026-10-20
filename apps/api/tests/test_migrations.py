from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.db import Base
from app.models import Project, User
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session


def test_project_retry_migration_roundtrip(database):
    # The database fixture owns a disposable SQLite DB or unique PostgreSQL schema.
    # Never run this against the configured application database.
    engine = database.kw["bind"]
    Base.metadata.drop_all(engine)
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "apps/api/alembic"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001")
        with Session(connection) as db:
            db.execute(
                User.__table__.insert().values(
                    id="migration-user",
                    email="migration@example.com",
                    display_name="Migration",
                    password_hash="unused",
                )
            )
            connection.execute(
                text(
                    "INSERT INTO projects "
                    "(id, name, description, owner_id, status, revision, created_at) "
                    "VALUES ('existing-project', 'Existing project', '', "
                    "'migration-user', 'active', 1, :created_at)"
                ),
                {"created_at": datetime.now(UTC)},
            )
            db.commit()
        command.upgrade(config, "head")
        command.check(config)
        assert "project_creation_requests" in inspect(connection).get_table_names()
        assert "requirement_embeddings" in inspect(connection).get_table_names()
        assert {
            "outcome",
        } <= {column["name"] for column in inspect(connection).get_columns("analysis_runs")}
        assert {
            "request_index",
            "input_span_start",
            "input_span_end",
        } <= {column["name"] for column in inspect(connection).get_columns("findings")}
        assert (
            connection.scalar(
                select(Project.external_ai_consent).where(Project.id == "existing-project")
            )
            is False
        )
        connection.execute(
            text(
                "INSERT INTO requirements "
                "(id, project_id, code, current_version, status, created_at) "
                "VALUES (:id, :project_id, :code, :version, :status, :created_at)"
            ),
            {
                "id": "migration-requirement",
                "project_id": "existing-project",
                "code": "REQ-001",
                "version": 1,
                "status": "active",
                "created_at": datetime.now(UTC),
            },
        )
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(
                text(
                    "UPDATE requirements SET status = 'invalid' WHERE id = 'migration-requirement'"
                )
            )
        command.downgrade(config, "0001")
        assert "project_creation_requests" not in inspect(connection).get_table_names()
        assert connection.scalar(select(Project.name)) == "Existing project"
        command.upgrade(config, "head")
        command.check(config)
        command.downgrade(config, "base")
        assert set(inspect(connection).get_table_names()) <= {"alembic_version"}
