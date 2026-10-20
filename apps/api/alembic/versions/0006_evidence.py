"""manual delivery artifacts and traceability links"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "delivery_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("external_id", sa.String(120), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("url", sa.String(1000)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.UniqueConstraint("project_id", "provider", "kind", "external_id"),
        sa.CheckConstraint("kind IN ('task','test','pull_request')"),
    )
    op.create_index("ix_delivery_artifacts_project_id", "delivery_artifacts", ["project_id"])
    op.create_index(
        "uq_artifact_project_id", "delivery_artifacts", ["project_id", "id"], unique=True
    )
    op.create_table(
        "artifact_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("requirement_version_id", sa.String(36), nullable=False),
        sa.Column("artifact_id", sa.String(36), nullable=False),
        sa.Column("relation_type", sa.String(24), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("review_status", sa.String(16), nullable=False),
        sa.Column("reviewed_by", sa.String(36)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["project_id", "requirement_version_id"],
            ["requirement_versions.project_id", "requirement_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "artifact_id"],
            ["delivery_artifacts.project_id", "delivery_artifacts.id"],
        ),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.UniqueConstraint("project_id", "requirement_version_id", "artifact_id"),
        sa.CheckConstraint("review_status IN ('proposed','accepted','rejected')"),
    )
    op.create_index("ix_artifact_links_project_id", "artifact_links", ["project_id"])


def downgrade():
    op.drop_index("ix_artifact_links_project_id", table_name="artifact_links")
    op.drop_table("artifact_links")
    op.drop_index("ix_delivery_artifacts_project_id", table_name="delivery_artifacts")
    op.drop_table("delivery_artifacts")
