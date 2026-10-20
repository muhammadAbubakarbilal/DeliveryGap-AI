"""Persist bounded change-request segments and explicit analysis outcomes."""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "analysis_runs",
        sa.Column(
            "outcome",
            sa.String(32),
            nullable=False,
            server_default="completed",
        ),
    )
    op.add_column("findings", sa.Column("request_index", sa.Integer(), nullable=True))
    op.add_column("findings", sa.Column("input_span_start", sa.Integer(), nullable=True))
    op.add_column("findings", sa.Column("input_span_end", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("findings", "input_span_end")
    op.drop_column("findings", "input_span_start")
    op.drop_column("findings", "request_index")
    op.drop_column("analysis_runs", "outcome")
