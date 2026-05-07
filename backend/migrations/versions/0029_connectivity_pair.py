"""connectivity_pair: Fase 18 extension — análise ponto-a-ponto entre dois firewalls

Revision ID: 0029
Revises: 0028
Create Date: 2026-05-07
"""
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE connectivity_analyses
            ADD COLUMN IF NOT EXISTS mode         TEXT NOT NULL DEFAULT 'single',
            ADD COLUMN IF NOT EXISTS device_b_id  UUID REFERENCES devices(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS device_b_routes         JSONB,
            ADD COLUMN IF NOT EXISTS device_b_bgp_peers      JSONB,
            ADD COLUMN IF NOT EXISTS device_b_ospf_neighbors JSONB,
            ADD COLUMN IF NOT EXISTS device_b_sdwan_services JSONB
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_connectivity_analyses_device_b_id "
        "ON connectivity_analyses(device_b_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_connectivity_analyses_device_b_id")
    op.execute("""
        ALTER TABLE connectivity_analyses
            DROP COLUMN IF EXISTS mode,
            DROP COLUMN IF EXISTS device_b_id,
            DROP COLUMN IF EXISTS device_b_routes,
            DROP COLUMN IF EXISTS device_b_bgp_peers,
            DROP COLUMN IF EXISTS device_b_ospf_neighbors,
            DROP COLUMN IF EXISTS device_b_sdwan_services
    """)
