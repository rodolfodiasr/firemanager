"""Fase 27 — VM Migration Planner tables.

Revision ID: 0040
Revises: 0038
Create Date: 2026-05-08
"""
from alembic import op
from sqlalchemy import text

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text("""
        CREATE TABLE vm_hypervisors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            hypervisor_type VARCHAR(30) NOT NULL,
            host VARCHAR(500) NOT NULL,
            encrypted_credentials TEXT NOT NULL,
            verify_ssl BOOLEAN NOT NULL DEFAULT FALSE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            last_sync_at TIMESTAMPTZ,
            last_vm_count INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    op.execute(text("CREATE INDEX ix_vm_hypervisors_tenant_id ON vm_hypervisors(tenant_id)"))

    op.execute(text("""
        CREATE TABLE vm_inventory (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            hypervisor_id UUID NOT NULL REFERENCES vm_hypervisors(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            vm_id VARCHAR(200) NOT NULL,
            vm_name VARCHAR(500) NOT NULL,
            power_state VARCHAR(20),
            os_type VARCHAR(200),
            cpu_count INTEGER,
            ram_mb INTEGER,
            disk_gb DOUBLE PRECISION,
            ip_addresses JSONB,
            tags JSONB,
            extra JSONB,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    op.execute(text("CREATE INDEX ix_vm_inventory_hypervisor_id ON vm_inventory(hypervisor_id)"))

    op.execute(text("CREATE INDEX ix_vm_inventory_tenant_id ON vm_inventory(tenant_id)"))

    op.execute(text("""
        CREATE TABLE migration_runbooks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            title VARCHAR(500) NOT NULL,
            vm_ids JSONB NOT NULL DEFAULT '[]',
            ai_runbook TEXT,
            source_hypervisor_id UUID REFERENCES vm_hypervisors(id) ON DELETE SET NULL,
            target_hypervisor_id UUID REFERENCES vm_hypervisors(id) ON DELETE SET NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            bookstack_page_url VARCHAR(500),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    op.execute(text("CREATE INDEX ix_migration_runbooks_tenant_id ON migration_runbooks(tenant_id)"))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS migration_runbooks"))
    op.execute(text("DROP TABLE IF EXISTS vm_inventory"))
    op.execute(text("DROP TABLE IF EXISTS vm_hypervisors"))
