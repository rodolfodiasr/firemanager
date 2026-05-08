"""Fase 23 — Alert channels, rules, and events.

Revision ID: 0037
Revises: 0036
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text("""
        CREATE TABLE alert_channels (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            channel_type VARCHAR(20) NOT NULL,
            encrypted_config TEXT NOT NULL DEFAULT '{}',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    op.execute(text("CREATE INDEX ix_alert_channels_tenant_id ON alert_channels(tenant_id)"))

    op.execute(text("""
        CREATE TABLE alert_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            trigger VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL DEFAULT 'warning',
            channel_ids JSONB NOT NULL DEFAULT '[]',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    op.execute(text("CREATE INDEX ix_alert_rules_tenant_id ON alert_rules(tenant_id)"))

    op.execute(text("""
        CREATE TABLE alert_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            rule_id UUID,
            trigger VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            title VARCHAR(256) NOT NULL,
            body TEXT NOT NULL,
            channels_result JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    op.execute(text("CREATE INDEX ix_alert_events_tenant_id ON alert_events(tenant_id)"))
    op.execute(text("CREATE INDEX ix_alert_events_created_at ON alert_events(created_at DESC)"))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS alert_events"))
    op.execute(text("DROP TABLE IF EXISTS alert_rules"))
    op.execute(text("DROP TABLE IF EXISTS alert_channels"))
