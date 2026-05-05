"""compliance: add device_id + device_type; make server_id nullable

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Make server_id nullable (network devices don't have a server_id)
    op.alter_column("compliance_reports", "server_id", nullable=True)

    # 2. Add device_id FK to devices (nullable — server reports leave this NULL)
    op.add_column(
        "compliance_reports",
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_compliance_reports_device_id",
        "compliance_reports", "devices",
        ["device_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_compliance_reports_device_id", "compliance_reports", ["device_id"])

    # 3. Add device_type to distinguish firewall vs switch in the UI
    op.add_column(
        "compliance_reports",
        sa.Column("device_type", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("compliance_reports", "device_type")
    op.drop_index("ix_compliance_reports_device_id", table_name="compliance_reports")
    op.drop_constraint("fk_compliance_reports_device_id", "compliance_reports", type_="foreignkey")
    op.drop_column("compliance_reports", "device_id")
    op.alter_column("compliance_reports", "server_id", nullable=False)
