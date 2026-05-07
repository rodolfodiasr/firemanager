"""firewall_migrations: Fase 16 — firewall rule migration table

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE firewall_migration_status AS ENUM
        ('pending','analyzing','ready','applying','completed','failed')
    """)
    op.create_table(
        "firewall_migrations",
        sa.Column("id",               UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id",        UUID(as_uuid=True), sa.ForeignKey("tenants.id",  ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id",  ondelete="SET NULL"), nullable=True),
        sa.Column("target_device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id",  ondelete="SET NULL"), nullable=True),
        sa.Column("source_vendor",    sa.String(50),  nullable=False),
        sa.Column("target_vendor",    sa.String(50),  nullable=False),
        sa.Column("status",           sa.Enum("pending","analyzing","ready","applying","completed","failed",
                                              name="firewall_migration_status", create_type=False),
                  nullable=False, server_default="pending"),
        sa.Column("source_rules_raw", sa.Text,   nullable=True),
        sa.Column("migration_plan",   JSONB,      nullable=True),
        sa.Column("commands_preview", sa.Text,   nullable=True),
        sa.Column("warnings",         JSONB,      nullable=True),
        sa.Column("error_message",    sa.Text,   nullable=True),
        sa.Column("created_at",       sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at",       sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("firewall_migrations")
    op.execute("DROP TYPE IF EXISTS firewall_migration_status")
