"""add tenant_variables and device_variables tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_variables",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "variable_type",
            sa.Enum(
                "string", "network", "ip", "port", "interface", "zone", "hostname", "gateway",
                name="variabletype",
                native_enum=False,
            ),
            nullable=False,
            server_default="string",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_tenant_variable_name"),
    )
    op.create_index("ix_tenant_variables_tenant_id", "tenant_variables", ["tenant_id"])

    op.create_table(
        "device_variables",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("device_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "variable_type",
            sa.Enum(
                "string", "network", "ip", "port", "interface", "zone", "hostname", "gateway",
                name="variabletype",
                native_enum=False,
            ),
            nullable=False,
            server_default="string",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "name", name="uq_device_variable_name"),
    )
    op.create_index("ix_device_variables_device_id", "device_variables", ["device_id"])
    op.create_index("ix_device_variables_tenant_id", "device_variables", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_device_variables_tenant_id", "device_variables")
    op.drop_index("ix_device_variables_device_id", "device_variables")
    op.drop_table("device_variables")
    op.drop_index("ix_tenant_variables_tenant_id", "tenant_variables")
    op.drop_table("tenant_variables")
