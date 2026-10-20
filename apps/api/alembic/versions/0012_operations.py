"""Persist import previews, queue commands, and immutable report snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_operations_project_id", "operations", ["project_id"])
    op.create_table(
        "report_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "operation_id",
            sa.String(36),
            sa.ForeignKey("operations.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_report_snapshots_project_id", "report_snapshots", ["project_id"])
    for event in ("UPDATE", "DELETE"):
        name = f"guard_report_snapshots_{event.lower()}"
        if op.get_bind().dialect.name == "postgresql":
            op.execute(
                f"CREATE FUNCTION {name}() RETURNS trigger AS $$ BEGIN "
                "RAISE EXCEPTION 'Immutable report'; END; $$ LANGUAGE plpgsql"
            )
            op.execute(
                f"CREATE TRIGGER {name} BEFORE {event} ON report_snapshots "
                f"FOR EACH ROW EXECUTE FUNCTION {name}()"
            )
        else:
            op.execute(
                f"CREATE TRIGGER {name} BEFORE {event} ON report_snapshots "
                "BEGIN SELECT RAISE(ABORT, 'Immutable report'); END"
            )


def downgrade():
    op.drop_table("report_snapshots")
    if op.get_bind().dialect.name == "postgresql":
        for event in ("update", "delete"):
            op.execute(f"DROP FUNCTION guard_report_snapshots_{event}()")
    op.drop_table("operations")
