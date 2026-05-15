"""F49 — GLPI Plugin Widget: tokens de acesso ao widget embed do Eternity no GLPI.

Revision ID: 0072
Revises: 0071
"""
from alembic import op

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS glpi_widget_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            glpi_integration_id UUID REFERENCES glpi_integrations(id) ON DELETE CASCADE,
            token_hash VARCHAR(64) NOT NULL UNIQUE,
            object_type VARCHAR(50) NOT NULL,
            object_id INTEGER,
            created_by UUID,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_glpi_widget_tokens_tenant_id ON glpi_widget_tokens(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_glpi_widget_tokens_token_hash ON glpi_widget_tokens(token_hash)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS glpi_widget_tokens")
