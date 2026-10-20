"""Persist requirement embeddings and incoming-source evidence for AI proposals."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        lakebase_vector = bind.scalar(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM pg_available_extensions "
                "WHERE name = 'lakebase_vector')"
            )
        )
        extension = "lakebase_vector" if lakebase_vector else "vector"
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {extension} CASCADE")
        embedding_type = Vector(1024)
    else:
        embedding_type = sa.JSON()

    op.add_column("findings", sa.Column("input_quote", sa.Text(), nullable=True))
    op.create_table(
        "requirement_embeddings",
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("requirement_version_id", sa.String(36), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("embedding", embedding_type, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "requirement_version_id"],
            ["requirement_versions.project_id", "requirement_versions.id"],
        ),
        sa.PrimaryKeyConstraint("project_id", "requirement_version_id", "model"),
    )
    op.create_index(
        "ix_requirement_embeddings_project_model",
        "requirement_embeddings",
        ["project_id", "model"],
    )


def downgrade():
    op.drop_index("ix_requirement_embeddings_project_model", table_name="requirement_embeddings")
    op.drop_table("requirement_embeddings")
    op.drop_column("findings", "input_quote")
