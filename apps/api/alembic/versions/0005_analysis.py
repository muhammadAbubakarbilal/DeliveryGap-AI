"""deterministic baseline analysis and finding decisions"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("baseline_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(
            ["project_id", "baseline_id"], ["baselines.project_id", "baselines.id"]
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.CheckConstraint("status = 'succeeded'"),
    )
    op.create_index("ix_analysis_runs_project_id", "analysis_runs", ["project_id"])
    op.create_table(
        "findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("requirement_version_id", sa.String(36)),
        sa.Column("evidence_quote", sa.Text()),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"]),
        sa.ForeignKeyConstraint(
            ["project_id", "requirement_version_id"],
            ["requirement_versions.project_id", "requirement_versions.id"],
        ),
        sa.UniqueConstraint("project_id", "id"),
        sa.CheckConstraint(
            "classification IN ("
            "'IN_SCOPE','POTENTIAL_SCOPE_ADDITION','CONFLICT','AMBIGUOUS','INSUFFICIENT_EVIDENCE')"
        ),
        sa.CheckConstraint(
            "review_status IN ('pending','confirmed','dismissed','clarification_requested')"
        ),
    )
    op.create_index("ix_findings_project_id", "findings", ["project_id"])
    op.create_table(
        "finding_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("finding_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("expected_status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id", "finding_id"], ["findings.project_id", "findings.id"]
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.CheckConstraint("decision IN ('confirmed','dismissed','clarification_requested')"),
    )
    op.create_index("ix_finding_decisions_project_id", "finding_decisions", ["project_id"])


def downgrade():
    op.drop_index("ix_finding_decisions_project_id", table_name="finding_decisions")
    op.drop_table("finding_decisions")
    op.drop_index("ix_findings_project_id", table_name="findings")
    op.drop_table("findings")
    op.drop_index("ix_analysis_runs_project_id", table_name="analysis_runs")
    op.drop_table("analysis_runs")
