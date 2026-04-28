"""add analysis_sessions table

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("sources_used", JSONB(), nullable=False, server_default="[]"),
        sa.Column("server_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("integration_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("host_filter", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_sessions_tenant_id", "analysis_sessions", ["tenant_id"])
    op.create_index("ix_analysis_sessions_created_at", "analysis_sessions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_analysis_sessions_created_at", "analysis_sessions")
    op.drop_index("ix_analysis_sessions_tenant_id", "analysis_sessions")
    op.drop_table("analysis_sessions")
