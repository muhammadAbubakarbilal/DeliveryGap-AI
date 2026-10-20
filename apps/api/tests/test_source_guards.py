from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.db import Base
from app.models import Project, User
from app.operation_models import Operation, ReportSnapshot
from app.source_models import Document, DocumentVersion, SourceSpan
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session


def test_migrated_source_original_and_spans_are_immutable(database):
    engine = database.kw["bind"]
    Base.metadata.drop_all(engine)
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "apps/api/alembic"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with Session(engine) as db:
        db.add(
            User(id="u", email="source@example.com", display_name="User", password_hash="unused")
        )
        db.flush()
        db.add(Project(id="p", name="Guard test", owner_id="u"))
        db.flush()
        db.add(Document(id="d", project_id="p", title="Scope", kind="scope"))
        db.flush()
        db.add(
            DocumentVersion(
                id="v",
                project_id="p",
                document_id="d",
                version_number=1,
                filename="scope.txt",
                mime_type="text/plain",
                sha256="a" * 64,
                storage_key="original",
                byte_size=4,
                uploaded_by="u",
                status="ready",
            )
        )
        db.flush()
        db.add(
            SourceSpan(
                id="s",
                project_id="p",
                version_id="v",
                ordinal=1,
                locator="Line 1",
                text="Text",
                char_end=4,
            )
        )
        db.add(
            Operation(
                id="op", project_id="p", actor_id="u", kind="report", status="succeeded", payload={}
            )
        )
        db.flush()
        db.add(
            ReportSnapshot(id="report", project_id="p", operation_id="op", payload={"frozen": True})
        )
        db.commit()
    for statement in [
        "UPDATE document_versions SET sha256 = 'changed'",
        "UPDATE document_versions SET uploaded_by = 'other'",
        "DELETE FROM document_versions",
        "UPDATE source_spans SET text = 'fake'",
        "DELETE FROM source_spans",
        "UPDATE report_snapshots SET payload = '{}'",
        "DELETE FROM report_snapshots",
    ]:
        with engine.connect() as connection, pytest.raises(DBAPIError), connection.begin():
            connection.execute(text(statement))
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE document_versions SET warning = 'allowed operational state'")
        )
