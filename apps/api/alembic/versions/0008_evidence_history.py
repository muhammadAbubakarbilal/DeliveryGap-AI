"""Preserve artifact revisions and link review decisions."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("delivery_artifacts", "artifact_links"):
        op.add_column(
            table, sa.Column("revision", sa.Integer(), nullable=False, server_default="1")
        )
    op.create_table(
        "artifact_revisions",
        sa.Column("artifact_id", sa.String(36), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id", "artifact_id"],
            ["delivery_artifacts.project_id", "delivery_artifacts.id"],
        ),
    )
    op.create_table(
        "link_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("link_id", sa.String(36), sa.ForeignKey("artifact_links.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("link_id", "revision"),
    )
    bind = op.get_bind()
    metadata = sa.MetaData()
    artifacts = sa.Table("delivery_artifacts", metadata, autoload_with=bind)
    revisions = sa.Table("artifact_revisions", metadata, autoload_with=bind)
    for row in bind.execute(sa.select(artifacts)).mappings():
        snapshot = dict(row)
        snapshot.pop("project_id")
        snapshot["updated_at"] = row["updated_at"].isoformat()
        bind.execute(
            revisions.insert().values(
                artifact_id=row["id"],
                revision=1,
                project_id=row["project_id"],
                actor_id=None,
                snapshot=snapshot,
                created_at=row["updated_at"],
            )
        )
    for table in ("artifact_revisions", "link_decisions"):
        for event in ("UPDATE", "DELETE"):
            name = f"guard_{table}_{event.lower()}"
            if op.get_bind().dialect.name == "postgresql":
                op.execute(f"""CREATE FUNCTION {name}() RETURNS trigger AS $$
                    BEGIN RAISE EXCEPTION 'Immutable history violation';
                    END; $$ LANGUAGE plpgsql""")
                op.execute(
                    f"CREATE TRIGGER {name} BEFORE {event} ON {table} "
                    f"FOR EACH ROW EXECUTE FUNCTION {name}()"
                )
            else:
                op.execute(
                    f"CREATE TRIGGER {name} BEFORE {event} ON {table} "
                    "BEGIN SELECT RAISE(ABORT, 'Immutable history violation'); END"
                )


def downgrade():
    for table in ("link_decisions", "artifact_revisions"):
        op.drop_table(table)
        if op.get_bind().dialect.name == "postgresql":
            for event in ("update", "delete"):
                op.execute(f"DROP FUNCTION guard_{table}_{event}()")
    for table in ("artifact_links", "delivery_artifacts"):
        op.drop_column(table, "revision")
