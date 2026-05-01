"""device category enum refactor + user_device_category_roles table

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-01

Changes:
  - DeviceCategory: router → routing, l3_switch → routing (data migration)
  - DeviceCategory: add server, hypervisor
  - New table: user_device_category_roles
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Migrate existing category values ───────────────────────────────────
    # category is stored as VARCHAR (native_enum=False), so plain UPDATE works.
    op.execute("UPDATE devices SET category = 'routing' WHERE category IN ('router', 'l3_switch')")

    # ── 2. user_device_category_roles table ───────────────────────────────────
    op.create_table(
        "user_device_category_roles",
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                  nullable=False, primary_key=True),
        sa.Column("category", sa.String(30), nullable=False, primary_key=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("granted_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_user_device_category_roles_tenant_id",
        "user_device_category_roles",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_device_category_roles_tenant_id",
                  table_name="user_device_category_roles")
    op.drop_table("user_device_category_roles")

    # Revert routing → router (l3_switch data is lost — acceptable for downgrade)
    op.execute("UPDATE devices SET category = 'router' WHERE category = 'routing'")
    op.execute("UPDATE devices SET category = 'firewall' WHERE category IN ('server', 'hypervisor')")
