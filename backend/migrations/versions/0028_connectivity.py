"""connectivity_analyses: Fase 18 — Network Connectivity Analysis

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum idempotently, then table in pure SQL to avoid SQLAlchemy
    # auto-triggering a second CREATE TYPE via sa.Enum in op.create_table.
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE connectivity_status AS ENUM ('pending', 'running', 'completed', 'failed');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS connectivity_analyses (
            id              UUID PRIMARY KEY,
            tenant_id       UUID REFERENCES tenants(id)  ON DELETE CASCADE,
            device_id       UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
            status          connectivity_status NOT NULL DEFAULT 'pending',
            routes          JSONB,
            bgp_peers       JSONB,
            ospf_neighbors  JSONB,
            sdwan_services  JSONB,
            anomalies       JSONB,
            ai_summary      TEXT,
            ai_recommendations JSONB,
            error           TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at    TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_connectivity_analyses_tenant_id ON connectivity_analyses(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_connectivity_analyses_device_id ON connectivity_analyses(device_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS connectivity_analyses")
    op.execute("DROP TYPE IF EXISTS connectivity_status")
