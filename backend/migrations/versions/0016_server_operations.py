"""Add server_operations table

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-02

Changes:
  - Create server_operations table for server Modo Técnico
    (tenant_id, user_id, server_id, description, commands, output, status, review fields)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "server_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("server_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("commands", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.VARCHAR(length=32),
            nullable=False,
            server_default="pending_review",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("requester_name", sa.VARCHAR(length=200), nullable=True),
        sa.Column("requester_email", sa.VARCHAR(length=255), nullable=True),
        sa.Column("server_name", sa.VARCHAR(length=100), nullable=True),
        sa.Column("server_host", sa.VARCHAR(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"],   ["users.id"],   ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_server_operations_tenant_id", "server_operations", ["tenant_id"])
    op.create_index("ix_server_operations_user_id",   "server_operations", ["user_id"])
    op.create_index("ix_server_operations_server_id", "server_operations", ["server_id"])
    op.create_index("ix_server_operations_status",    "server_operations", ["status"])
    op.create_index("ix_server_operations_created_at","server_operations", ["created_at"])


def downgrade() -> None:
    op.drop_table("server_operations")
