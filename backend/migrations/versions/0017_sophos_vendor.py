"""Add sophos to VendorEnum

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-03

Changes:
  - VendorEnum: add sophos = "sophos"
  - vendor column is String(30) (native_enum=False) — no schema change required
"""
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # vendor is stored as VARCHAR(30) — inserting "sophos" requires no DDL change.
    pass


def downgrade() -> None:
    op.execute("UPDATE devices SET vendor = 'fortinet' WHERE vendor = 'sophos'")
