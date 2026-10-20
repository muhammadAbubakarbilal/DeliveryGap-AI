"""requirements and published baselines"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.UniqueConstraint("project_id", "id"),
        sa.UniqueConstraint("project_id", "code"),
    )
    op.create_index("ix_requirements_project_id", "requirements", ["project_id"])
    op.create_table(
        "requirement_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("requirement_id", sa.String(36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source_version_id", sa.String(36)),
        sa.Column("source_span_id", sa.String(36)),
        sa.Column("source_quote", sa.Text()),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id", "requirement_id"], ["requirements.project_id", "requirements.id"]
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "source_version_id"],
            ["document_versions.project_id", "document_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "source_span_id"], ["source_spans.project_id", "source_spans.id"]
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.UniqueConstraint("requirement_id", "version_number"),
        sa.UniqueConstraint("project_id", "id"),
        sa.CheckConstraint("version_number > 0"),
        sa.CheckConstraint("status IN ('draft','approved','rejected')"),
    )
    op.create_index("ix_requirement_versions_project_id", "requirement_versions", ["project_id"])
    op.create_table(
        "requirement_review_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("requirement_version_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id", "requirement_version_id"],
            ["requirement_versions.project_id", "requirement_versions.id"],
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.CheckConstraint("action IN ('approved','rejected')"),
    )
    op.create_index(
        "ix_requirement_review_events_project_id",
        "requirement_review_events",
        ["project_id"],
    )
    op.create_table(
        "baselines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("published_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"]),
        sa.UniqueConstraint("project_id", "number"),
        sa.UniqueConstraint("project_id", "id"),
        sa.CheckConstraint("number > 0"),
        sa.CheckConstraint("status = 'published'"),
    )
    op.create_index("ix_baselines_project_id", "baselines", ["project_id"])
    op.create_table(
        "baseline_items",
        sa.Column("baseline_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("requirement_version_id", sa.String(36), primary_key=True),
        sa.Column("requirement_code", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id", "baseline_id"], ["baselines.project_id", "baselines.id"]
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "requirement_version_id"],
            ["requirement_versions.project_id", "requirement_versions.id"],
        ),
    )


def downgrade():
    op.drop_table("baseline_items")
    op.drop_index("ix_baselines_project_id", table_name="baselines")
    op.drop_table("baselines")
    op.drop_index("ix_requirement_review_events_project_id", table_name="requirement_review_events")
    op.drop_table("requirement_review_events")
    op.drop_index("ix_requirement_versions_project_id", table_name="requirement_versions")
    op.drop_table("requirement_versions")
    op.drop_index("ix_requirements_project_id", table_name="requirements")
    op.drop_table("requirements")
