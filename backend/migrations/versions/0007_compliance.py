"""add compliance_reports table

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "compliance_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("server_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("agent_id", sa.String(64), nullable=True),
        sa.Column("policy_id", sa.String(128), nullable=True),
        sa.Column("policy_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("score_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_checks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("not_applicable", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("controls", JSONB(), nullable=False, server_default="[]"),
        sa.Column("ai_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("ai_recommendations", JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compliance_reports_tenant_id", "compliance_reports", ["tenant_id"])
    op.create_index("ix_compliance_reports_server_id", "compliance_reports", ["server_id"])
    op.create_index("ix_compliance_reports_created_at", "compliance_reports", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_compliance_reports_created_at", "compliance_reports")
    op.drop_index("ix_compliance_reports_server_id", "compliance_reports")
    op.drop_index("ix_compliance_reports_tenant_id", "compliance_reports")
    op.drop_table("compliance_reports")
