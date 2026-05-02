"""Add user_functional_module_roles table

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-02

Changes:
  - Create user_functional_module_roles table
    (user_id, tenant_id, module, role, granted_by, created_at)
  - Supported modules: compliance, remediation, server_analysis, bulk_jobs
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_functional_module_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module", sa.VARCHAR(length=32), nullable=False),
        sa.Column("role", sa.VARCHAR(length=32), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "tenant_id", "module"),
    )
    op.create_index(
        "ix_user_functional_module_roles_tenant_id",
        "user_functional_module_roles",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_functional_module_roles_tenant_id", table_name="user_functional_module_roles")
    op.drop_table("user_functional_module_roles")
