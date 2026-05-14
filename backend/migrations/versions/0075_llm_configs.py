"""llm_configs: multi-provider LLM configuration — global (super admin) e por tenant.

Revision ID: 0075
Revises: 0074
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("api_key_encrypted", sa.Text, nullable=True),
        sa.Column("api_base_url", sa.String(500), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("no_train_flag", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_llm_configs_tenant_id", "llm_configs", ["tenant_id"])
    op.create_index("ix_llm_configs_provider", "llm_configs", ["provider"])


def downgrade() -> None:
    op.drop_index("ix_llm_configs_provider", table_name="llm_configs")
    op.drop_index("ix_llm_configs_tenant_id", table_name="llm_configs")
    op.drop_table("llm_configs")
