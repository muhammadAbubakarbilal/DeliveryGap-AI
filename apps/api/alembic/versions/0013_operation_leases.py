"""Fence provider operations while network work runs outside database transactions."""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("operations", sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("operations", sa.Column("fence", sa.String(36), nullable=True))


def downgrade():
    op.drop_column("operations", "fence")
    op.drop_column("operations", "lease_until")
