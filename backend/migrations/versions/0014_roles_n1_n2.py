"""Add analyst_n1 and analyst_n2 roles

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-02

Changes:
  - Add 'analyst_n1' and 'analyst_n2' values to tenant_role enum
  - Existing 'analyst' rows are migrated to 'analyst_n2'
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # user_tenant_roles uses native_enum=False so the column is VARCHAR — just add new values
    # by altering existing data and updating CHECK constraint if any.
    # Since the column was created with Enum(TenantRole, native_enum=False) it's a plain VARCHAR
    # with no PG enum type — we only need to migrate existing data.

    # Migrate legacy 'analyst' → 'analyst_n2'
    op.execute(
        "UPDATE user_tenant_roles SET role = 'analyst_n2' WHERE role = 'analyst'"
    )

    # Same migration for user_device_category_roles if it stores roles
    op.execute(
        "UPDATE user_device_category_roles SET role = 'analyst_n2' WHERE role = 'analyst'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE user_tenant_roles SET role = 'analyst' WHERE role IN ('analyst_n1', 'analyst_n2')"
    )
    op.execute(
        "UPDATE user_device_category_roles SET role = 'analyst' WHERE role IN ('analyst_n1', 'analyst_n2')"
    )
