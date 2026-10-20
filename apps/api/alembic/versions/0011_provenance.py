"""Protect canonical sources and retain the artifact revision inspected by reviewers."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

TABLES = ("source_spans", "document_chunks")
COLUMNS = (
    "id",
    "project_id",
    "document_id",
    "version_number",
    "filename",
    "mime_type",
    "sha256",
    "storage_key",
    "byte_size",
    "uploaded_by",
    "is_manual",
    "created_at",
)


def guards():
    operator = "IS DISTINCT FROM" if op.get_bind().dialect.name == "postgresql" else "IS NOT"
    yield (
        "source_original_update",
        "document_versions",
        "UPDATE",
        " OR ".join(f"OLD.{column} {operator} NEW.{column}" for column in COLUMNS),
    )
    yield "source_original_delete", "document_versions", "DELETE", "TRUE"
    for table in TABLES:
        for event in ("UPDATE", "DELETE"):
            yield f"{table}_{event.lower()}", table, event, "TRUE"


def upgrade():
    # Older reviews have no reliable inspected revision. Leave them unknown, never infer it.
    op.add_column("artifact_links", sa.Column("artifact_revision", sa.Integer(), nullable=True))
    op.add_column("link_decisions", sa.Column("artifact_revision", sa.Integer(), nullable=True))
    for name, table, event, condition in guards():
        if op.get_bind().dialect.name == "postgresql":
            op.execute(f"""CREATE FUNCTION guard_{name}() RETURNS trigger AS $$
                BEGIN IF {condition} THEN RAISE EXCEPTION 'Immutable source violation'; END IF;
                RETURN NEW; END; $$ LANGUAGE plpgsql""")
            op.execute(
                f"CREATE TRIGGER guard_{name} BEFORE {event} ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION guard_{name}()"
            )
        else:
            op.execute(
                f"CREATE TRIGGER guard_{name} BEFORE {event} ON {table} WHEN {condition} "
                "BEGIN SELECT RAISE(ABORT, 'Immutable source violation'); END"
            )


def downgrade():
    for name, table, _, _ in guards():
        if op.get_bind().dialect.name == "postgresql":
            op.execute(f"DROP TRIGGER guard_{name} ON {table}")
            op.execute(f"DROP FUNCTION guard_{name}()")
        else:
            op.execute(f"DROP TRIGGER guard_{name}")
    op.drop_column("link_decisions", "artifact_revision")
    op.drop_column("artifact_links", "artifact_revision")
