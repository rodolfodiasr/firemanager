"""Compliance & Governance module — trust_scores table + framework columns

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-03

Changes:
  - Create trust_scores table (per-framework historical snapshots)
  - Add framework and framework_version columns to compliance_reports
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── trust_scores table ────────────────────────────────────────────────────
    op.create_table(
        "trust_scores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("framework", sa.String(20), nullable=False),
        sa.Column("score_pct", sa.Float(), nullable=False),
        sa.Column("breakdown", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("narrative", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "computed_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trust_scores_tenant_id",   "trust_scores", ["tenant_id"])
    op.create_index("ix_trust_scores_framework",   "trust_scores", ["framework"])
    op.create_index("ix_trust_scores_computed_at", "trust_scores", ["computed_at"])

    # ── Add framework columns to compliance_reports ───────────────────────────
    op.add_column(
        "compliance_reports",
        sa.Column("framework", sa.String(20), nullable=False, server_default="cis_benchmark"),
    )
    op.create_index("ix_compliance_reports_framework", "compliance_reports", ["framework"])

    op.add_column(
        "compliance_reports",
        sa.Column("framework_version", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("compliance_reports", "framework_version")
    op.drop_index("ix_compliance_reports_framework", table_name="compliance_reports")
    op.drop_column("compliance_reports", "framework")
    op.drop_table("trust_scores")
