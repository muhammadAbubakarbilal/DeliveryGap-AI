"""Protect published scope and repair the artifact project reference target."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# SQL below contains only fixed schema identifiers, never submitted text.
APPEND_ONLY = ("baselines", "baseline_items", "requirement_review_events", "finding_decisions")


def guard(name, table, event, condition):
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"""CREATE FUNCTION {name}() RETURNS trigger AS $$
        BEGIN IF {condition} THEN RAISE EXCEPTION 'Immutable history violation'; END IF;
        RETURN NEW; END; $$ LANGUAGE plpgsql""")
        op.execute(
            f"CREATE TRIGGER {name} BEFORE {event} ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {name}()"
        )
    else:
        op.execute(
            f"CREATE TRIGGER {name} BEFORE {event} ON {table} WHEN {condition} "
            "BEGIN SELECT RAISE(ABORT, 'Immutable history violation'); END"
        )


def upgrade():
    # A unique index is a valid composite-FK target on both supported test dialects.
    indexes = sa.inspect(op.get_bind()).get_indexes("delivery_artifacts")
    if not any(index["name"] == "uq_artifact_project_id" for index in indexes):
        op.create_index(
            "uq_artifact_project_id", "delivery_artifacts", ["project_id", "id"], unique=True
        )
    for table in APPEND_ONLY:
        for event in ("UPDATE", "DELETE"):
            guard(f"guard_{table}_{event.lower()}", table, event, "TRUE")
    columns = (
        "id",
        "project_id",
        "requirement_id",
        "version_number",
        "title",
        "content",
        "source_version_id",
        "source_span_id",
        "source_quote",
        "created_by",
        "created_at",
    )
    operator = "IS DISTINCT FROM" if op.get_bind().dialect.name == "postgresql" else "IS NOT"
    changed = " OR ".join(f"OLD.{column} {operator} NEW.{column}" for column in columns)
    guard(
        "guard_requirement_content",
        "requirement_versions",
        "UPDATE",
        f"OLD.status <> 'draft' OR ({changed})",
    )
    guard("guard_requirement_delete", "requirement_versions", "DELETE", "TRUE")
    guard(
        "guard_baseline_item_insert",
        "baseline_items",
        "INSERT",
        """
        EXISTS (SELECT 1 FROM audit_events WHERE event_type = 'baseline.published'
                AND target_id = NEW.baseline_id AND project_id = NEW.project_id)
        OR NOT EXISTS (SELECT 1 FROM requirement_versions v JOIN requirements r
                       ON r.id = v.requirement_id AND r.project_id = v.project_id
                       WHERE v.id = NEW.requirement_version_id AND v.project_id = NEW.project_id
                       AND v.status = 'approved' AND r.code = NEW.requirement_code)
        OR EXISTS (SELECT 1 FROM baseline_items i JOIN requirement_versions oldv
                   ON oldv.id = i.requirement_version_id JOIN requirement_versions newv
                   ON newv.requirement_id = oldv.requirement_id
                   WHERE i.baseline_id = NEW.baseline_id AND newv.id = NEW.requirement_version_id)
    """,
    )


def downgrade():
    names = [
        (f"guard_{table}_{event}", table) for table in APPEND_ONLY for event in ("update", "delete")
    ]
    names += [
        ("guard_requirement_content", "requirement_versions"),
        ("guard_requirement_delete", "requirement_versions"),
        ("guard_baseline_item_insert", "baseline_items"),
    ]
    for name, table in names:
        if op.get_bind().dialect.name == "postgresql":
            op.execute(f"DROP TRIGGER {name} ON {table}")
            op.execute(f"DROP FUNCTION {name}()")
        else:
            op.execute(f"DROP TRIGGER {name}")
