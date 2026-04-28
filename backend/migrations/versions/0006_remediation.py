"""add remediation_plans and remediation_commands tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "remediation_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("server_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending_approval"),
        sa.Column("reviewer_comment", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["analysis_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_remediation_plans_tenant_id", "remediation_plans", ["tenant_id"])
    op.create_index("ix_remediation_plans_server_id", "remediation_plans", ["server_id"])
    op.create_index("ix_remediation_plans_status", "remediation_plans", ["status"])
    op.create_index("ix_remediation_plans_created_at", "remediation_plans", ["created_at"])

    op.create_table(
        "remediation_commands",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("risk", sa.String(16), nullable=False, server_default="low"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["remediation_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_remediation_commands_plan_id", "remediation_commands", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_remediation_commands_plan_id", "remediation_commands")
    op.drop_table("remediation_commands")

    op.drop_index("ix_remediation_plans_created_at", "remediation_plans")
    op.drop_index("ix_remediation_plans_status", "remediation_plans")
    op.drop_index("ix_remediation_plans_server_id", "remediation_plans")
    op.drop_index("ix_remediation_plans_tenant_id", "remediation_plans")
    op.drop_table("remediation_plans")
