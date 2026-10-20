"""Protect finding decisions against stale revisions."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "analysis_runs",
        sa.Column(
            "provider",
            sa.String(32),
            nullable=False,
            server_default="legacy_heuristic",
        ),
    )
    op.add_column(
        "findings", sa.Column("revision", sa.Integer(), nullable=False, server_default="1")
    )


def downgrade():
    op.drop_column("analysis_runs", "provider")
    op.drop_column("findings", "revision")
