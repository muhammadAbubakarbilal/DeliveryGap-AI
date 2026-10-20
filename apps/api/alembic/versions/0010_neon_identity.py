"""Bind managed identities explicitly to workspace users."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("neon_subject", sa.String(255), nullable=True))
    op.create_index("uq_users_neon_subject", "users", ["neon_subject"], unique=True)


def downgrade():
    op.drop_index("uq_users_neon_subject", table_name="users")
    op.drop_column("users", "neon_subject")
