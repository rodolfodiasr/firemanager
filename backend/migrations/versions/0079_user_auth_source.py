"""users: auth_source, ldap_dn, break_glass — suporte a autenticação mista local/LDAP/OIDC

Revision ID: 0079
Revises: 0078
"""
from alembic import op

revision = "0079"
down_revision = "0078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users: fonte de autenticação por usuário
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS auth_source VARCHAR(20) NOT NULL DEFAULT 'local',
        ADD COLUMN IF NOT EXISTS ldap_dn     TEXT,
        ADD COLUMN IF NOT EXISTS break_glass BOOLEAN NOT NULL DEFAULT FALSE
    """)

    # sso_configs: campo genérico para configurações específicas por provider
    # (LDAP: ldap_url, base_dn, bind_user, bind_password_encrypted, user_filter)
    # Condicional — tabela pode não existir se F31 não foi aplicada neste ambiente
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'sso_configs'
            ) THEN
                ALTER TABLE sso_configs
                ADD COLUMN IF NOT EXISTS extra_config JSONB;
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS auth_source")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS ldap_dn")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS break_glass")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'sso_configs'
            ) THEN
                ALTER TABLE sso_configs DROP COLUMN IF EXISTS extra_config;
            END IF;
        END $$
    """)
