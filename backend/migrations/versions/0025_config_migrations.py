"""config_migrations: switch configuration migration planning and apply

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "config_migrations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_device_id", UUID(as_uuid=True),
            sa.ForeignKey("devices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "target_device_id", UUID(as_uuid=True),
            sa.ForeignKey("devices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_vendor", sa.String(50), nullable=False),
        sa.Column("target_vendor", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("source_config_raw", sa.Text, nullable=True),
        sa.Column("target_config_raw", sa.Text, nullable=True),
        sa.Column("migration_plan", JSONB, nullable=True),
        sa.Column("port_mapping", JSONB, nullable=True),
        sa.Column("commands_preview", sa.Text, nullable=True),
        sa.Column("warnings", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_config_migrations_tenant_id", "config_migrations", ["tenant_id"])
    op.create_index("ix_config_migrations_status", "config_migrations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_config_migrations_status", "config_migrations")
    op.drop_index("ix_config_migrations_tenant_id", "config_migrations")
    op.drop_table("config_migrations")
