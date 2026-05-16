"""devices: add connection_mode and edge_agent_id for Edge Agent support

Revision ID: 0081
Revises: 0080
"""
from alembic import op

revision = "0081"
down_revision = "0080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE devices
        ADD COLUMN IF NOT EXISTS connection_mode VARCHAR(20) NOT NULL DEFAULT 'direct'
    """)
    # FK condicional — edge_agents só existe se a F31 (migration 0065) foi aplicada
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'edge_agents'
            ) THEN
                ALTER TABLE devices
                ADD COLUMN IF NOT EXISTS edge_agent_id UUID REFERENCES edge_agents(id) ON DELETE SET NULL;
            ELSE
                ALTER TABLE devices
                ADD COLUMN IF NOT EXISTS edge_agent_id UUID;
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE devices DROP COLUMN IF EXISTS connection_mode")
    op.execute("ALTER TABLE devices DROP COLUMN IF EXISTS edge_agent_id")
