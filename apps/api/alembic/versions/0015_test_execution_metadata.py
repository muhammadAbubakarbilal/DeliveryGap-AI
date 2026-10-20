"""Store manual and imported test execution metadata as structured fields."""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "delivery_artifacts",
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "delivery_artifacts",
        sa.Column("environment", sa.String(200), nullable=True),
    )


def downgrade():
    op.drop_column("delivery_artifacts", "environment")
    op.drop_column("delivery_artifacts", "executed_at")
