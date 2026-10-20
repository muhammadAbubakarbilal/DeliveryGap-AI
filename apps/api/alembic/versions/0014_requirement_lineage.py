"""Record split/merge lineage and exclude superseded scope from new baselines."""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def immutable_guard(name, table, event):
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            f"""CREATE FUNCTION {name}() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'Immutable requirement lineage'; END;
            $$ LANGUAGE plpgsql"""
        )
        op.execute(
            f"CREATE TRIGGER {name} BEFORE {event} ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {name}()"
        )
    else:
        op.execute(
            f"CREATE TRIGGER {name} BEFORE {event} ON {table} "
            "BEGIN SELECT RAISE(ABORT, 'Immutable requirement lineage'); END"
        )


def requirement_status_guard():
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """CREATE FUNCTION guard_requirement_status() RETURNS trigger AS $$
            BEGIN
                IF NEW.status NOT IN ('active','superseded') THEN
                    RAISE EXCEPTION 'Invalid requirement lifecycle status';
                END IF;
                RETURN NEW;
            END; $$ LANGUAGE plpgsql"""
        )
        op.execute(
            "CREATE TRIGGER guard_requirement_status "
            "BEFORE INSERT OR UPDATE OF status ON requirements "
            "FOR EACH ROW EXECUTE FUNCTION guard_requirement_status()"
        )
    else:
        for event in ("INSERT", "UPDATE OF status"):
            suffix = "insert" if event == "INSERT" else "update"
            op.execute(
                f"CREATE TRIGGER guard_requirement_status_{suffix} "
                f"BEFORE {event} ON requirements "
                "WHEN NEW.status NOT IN ('active','superseded') "
                "BEGIN SELECT RAISE(ABORT, 'Invalid requirement lifecycle status'); END"
            )


def active_baseline_guard():
    condition = """EXISTS (
        SELECT 1 FROM requirement_versions v JOIN requirements r
        ON r.project_id = v.project_id AND r.id = v.requirement_id
        WHERE v.project_id = NEW.project_id AND v.id = NEW.requirement_version_id
        AND r.status <> 'active'
    )"""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """CREATE FUNCTION guard_active_requirement_baseline_item() RETURNS trigger AS $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM requirement_versions v JOIN requirements r
                    ON r.project_id = v.project_id AND r.id = v.requirement_id
                    WHERE v.project_id = NEW.project_id AND v.id = NEW.requirement_version_id
                    AND r.status <> 'active'
                ) THEN RAISE EXCEPTION 'Superseded requirement cannot enter a baseline'; END IF;
                RETURN NEW;
            END; $$ LANGUAGE plpgsql"""
        )
        op.execute(
            "CREATE TRIGGER guard_active_requirement_baseline_item "
            "BEFORE INSERT ON baseline_items FOR EACH ROW "
            "EXECUTE FUNCTION guard_active_requirement_baseline_item()"
        )
    else:
        op.execute(
            "CREATE TRIGGER guard_active_requirement_baseline_item "
            f"BEFORE INSERT ON baseline_items WHEN {condition} "
            "BEGIN SELECT RAISE(ABORT, 'Superseded requirement cannot enter a baseline'); END"
        )


def upgrade():
    op.add_column(
        "requirements",
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
    )
    requirement_status_guard()
    op.create_table(
        "requirement_lineage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(8), nullable=False),
        sa.Column("parent_requirement_id", sa.String(36), nullable=False),
        sa.Column("parent_version_id", sa.String(36), nullable=False),
        sa.Column("child_requirement_id", sa.String(36), nullable=False),
        sa.Column("child_version_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id", "parent_requirement_id"], ["requirements.project_id", "requirements.id"]
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "child_requirement_id"], ["requirements.project_id", "requirements.id"]
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "parent_version_id"],
            ["requirement_versions.project_id", "requirement_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "child_version_id"],
            ["requirement_versions.project_id", "requirement_versions.id"],
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.UniqueConstraint(
            "project_id",
            "action",
            "parent_requirement_id",
            "child_requirement_id",
            name="uq_requirement_lineage_edge",
        ),
        sa.CheckConstraint("action IN ('split','merge')", name="ck_requirement_lineage_action"),
        sa.CheckConstraint(
            "parent_requirement_id <> child_requirement_id", name="ck_requirement_lineage_distinct"
        ),
    )
    op.create_index("ix_requirement_lineage_project_id", "requirement_lineage", ["project_id"])
    for event in ("UPDATE", "DELETE"):
        immutable_guard(f"guard_requirement_lineage_{event.lower()}", "requirement_lineage", event)
    active_baseline_guard()


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER guard_requirement_status ON requirements")
        op.execute("DROP FUNCTION guard_requirement_status()")
    else:
        op.execute("DROP TRIGGER guard_requirement_status_insert")
        op.execute("DROP TRIGGER guard_requirement_status_update")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER guard_active_requirement_baseline_item ON baseline_items")
        op.execute("DROP FUNCTION guard_active_requirement_baseline_item()")
        for event in ("update", "delete"):
            name = f"guard_requirement_lineage_{event}"
            op.execute(f"DROP TRIGGER {name} ON requirement_lineage")
            op.execute(f"DROP FUNCTION {name}()")
    else:
        op.execute("DROP TRIGGER guard_active_requirement_baseline_item")
        op.execute("DROP TRIGGER guard_requirement_lineage_update")
        op.execute("DROP TRIGGER guard_requirement_lineage_delete")
    op.drop_index("ix_requirement_lineage_project_id", table_name="requirement_lineage")
    op.drop_table("requirement_lineage")
    op.drop_column("requirements", "status")
