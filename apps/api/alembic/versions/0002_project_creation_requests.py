"""Durable project creation retries.

Revision ID: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_creation_requests",
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("request_key", sa.String(128), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False, unique=True
        ),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("project_creation_requests")
