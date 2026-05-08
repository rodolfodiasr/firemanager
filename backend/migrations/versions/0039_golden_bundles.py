"""Fase 26 — Golden Config Bundles REST-native.

Revision ID: 0039
Revises: 0038
Create Date: 2026-05-08
"""
from alembic import op
from sqlalchemy import text

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text("""
        CREATE TABLE golden_bundles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            vendor VARCHAR(30) NOT NULL,
            variables JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    op.execute(text("CREATE INDEX ix_golden_bundles_tenant_id ON golden_bundles(tenant_id)"))

    op.execute(text("""
        CREATE TABLE bundle_sections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bundle_id UUID NOT NULL REFERENCES golden_bundles(id) ON DELETE CASCADE,
            section_type VARCHAR(50) NOT NULL,
            template_id UUID REFERENCES golden_templates(id) ON DELETE SET NULL,
            rest_payload_template TEXT,
            apply_strategy VARCHAR(20) NOT NULL DEFAULT 'rest_api',
            apply_order INTEGER NOT NULL DEFAULT 0,
            rollback_strategy VARCHAR(30) NOT NULL DEFAULT 'none'
        )
    """))

    op.execute(text("""
        CREATE TABLE bundle_applies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bundle_id UUID NOT NULL REFERENCES golden_bundles(id) ON DELETE CASCADE,
            device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
            status VARCHAR(20) NOT NULL DEFAULT 'applying',
            variables_used JSONB,
            section_results JSONB,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """))

    op.execute(text("CREATE INDEX ix_bundle_applies_bundle_id ON bundle_applies(bundle_id)"))

    op.execute(text("CREATE INDEX ix_bundle_applies_device_id ON bundle_applies(device_id)"))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS bundle_applies"))
    op.execute(text("DROP TABLE IF EXISTS bundle_sections"))
    op.execute(text("DROP TABLE IF EXISTS golden_bundles"))
