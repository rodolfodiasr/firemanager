"""Fase 22 — Onboarding profiles and external connectors.

Revision ID: 0036
Revises: 0035
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text("""
        CREATE TABLE external_connectors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            connector_type VARCHAR(30) NOT NULL,
            encrypted_config TEXT NOT NULL DEFAULT '{}',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    op.execute(text("CREATE INDEX ix_external_connectors_tenant_id ON external_connectors(tenant_id)"))

    op.execute(text("""
        CREATE TABLE onboarding_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            ad_groups JSONB NOT NULL DEFAULT '[]',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    op.execute(text("CREATE INDEX ix_onboarding_profiles_tenant_id ON onboarding_profiles(tenant_id)"))

    op.execute(text("""
        CREATE TABLE onboarding_profile_systems (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            profile_id UUID NOT NULL REFERENCES onboarding_profiles(id) ON DELETE CASCADE,
            system_type VARCHAR(30) NOT NULL,
            system_id VARCHAR(36),
            system_name VARCHAR(256) NOT NULL,
            config JSONB NOT NULL DEFAULT '{}'
        )
    """))
    op.execute(text("CREATE INDEX ix_onboarding_profile_systems_profile_id ON onboarding_profile_systems(profile_id)"))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS onboarding_profile_systems"))
    op.execute(text("DROP TABLE IF EXISTS onboarding_profiles"))
    op.execute(text("DROP TABLE IF EXISTS external_connectors"))
