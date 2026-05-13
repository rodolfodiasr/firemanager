"""F36: Identity Governance — ad_users, ad_groups, memberships, sod, campaigns, jit.

Revision ID: 0053
Revises: 0052
Create Date: 2026-05-13
"""
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # identity_connectors — configuração de conexão AD/M365 por tenant
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS identity_connectors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            source VARCHAR(20) NOT NULL DEFAULT 'ad_ldap',
            config_encrypted TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_sync_at TIMESTAMPTZ,
            last_sync_status VARCHAR(30),
            last_sync_error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_id_conn_tenant ON identity_connectors(tenant_id)")

    # ------------------------------------------------------------------
    # ad_users — inventário de usuários AD/Azure AD
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS ad_users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            connector_id UUID NOT NULL REFERENCES identity_connectors(id) ON DELETE CASCADE,
            source VARCHAR(20) NOT NULL DEFAULT 'ad_ldap',
            object_id VARCHAR(200),
            upn VARCHAR(300) NOT NULL,
            sam_account VARCHAR(100),
            display_name VARCHAR(200),
            email VARCHAR(300),
            department VARCHAR(200),
            job_title VARCHAR(200),
            manager_upn VARCHAR(300),
            is_enabled BOOLEAN NOT NULL DEFAULT true,
            is_external BOOLEAN NOT NULL DEFAULT false,
            mfa_registered BOOLEAN,
            last_sign_in TIMESTAMPTZ,
            password_last_set TIMESTAMPTZ,
            created_at_ad TIMESTAMPTZ,
            license_skus JSONB NOT NULL DEFAULT '[]',
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, connector_id, upn)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ad_users_tenant ON ad_users(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ad_users_upn ON ad_users(tenant_id, upn)")

    # ------------------------------------------------------------------
    # ad_groups — inventário de grupos AD/Azure AD
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS ad_groups (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            connector_id UUID NOT NULL REFERENCES identity_connectors(id) ON DELETE CASCADE,
            source VARCHAR(20) NOT NULL DEFAULT 'ad_ldap',
            object_id VARCHAR(200),
            display_name VARCHAR(300) NOT NULL,
            dn TEXT,
            group_type VARCHAR(50),
            member_count INTEGER NOT NULL DEFAULT 0,
            owner_upns JSONB NOT NULL DEFAULT '[]',
            health_score INTEGER,
            health_issues JSONB NOT NULL DEFAULT '[]',
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, connector_id, display_name)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ad_groups_tenant ON ad_groups(tenant_id)")

    # ------------------------------------------------------------------
    # ad_group_memberships — usuário × grupo (snapshot)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS ad_group_memberships (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES ad_users(id) ON DELETE CASCADE,
            group_id UUID NOT NULL REFERENCES ad_groups(id) ON DELETE CASCADE,
            added_at TIMESTAMPTZ,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (user_id, group_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ad_membership_user ON ad_group_memberships(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ad_membership_group ON ad_group_memberships(group_id)")

    # ------------------------------------------------------------------
    # sod_rules — regras de Segregação de Funções
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS sod_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            role_a_type VARCHAR(30) NOT NULL DEFAULT 'group',
            role_a_name VARCHAR(300) NOT NULL,
            role_b_type VARCHAR(30) NOT NULL DEFAULT 'group',
            role_b_name VARCHAR(300) NOT NULL,
            risk_description TEXT,
            severity VARCHAR(20) NOT NULL DEFAULT 'high',
            remediation_suggestion TEXT,
            is_builtin BOOLEAN NOT NULL DEFAULT false,
            enabled BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_sod_rules_tenant ON sod_rules(tenant_id)")

    # ------------------------------------------------------------------
    # sod_violations — violações detectadas
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS sod_violations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES ad_users(id) ON DELETE CASCADE,
            rule_id UUID NOT NULL REFERENCES sod_rules(id) ON DELETE CASCADE,
            detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            status VARCHAR(30) NOT NULL DEFAULT 'open',
            accepted_by UUID REFERENCES users(id) ON DELETE SET NULL,
            accepted_reason TEXT,
            remediated_at TIMESTAMPTZ,
            UNIQUE (user_id, rule_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_sod_violations_tenant ON sod_violations(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sod_violations_status ON sod_violations(tenant_id, status)")

    # ------------------------------------------------------------------
    # access_campaigns — campanhas de revisão de acesso
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS access_campaigns (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            campaign_type VARCHAR(30) NOT NULL DEFAULT 'by_manager',
            scope_filter JSONB NOT NULL DEFAULT '{}',
            reviewer_type VARCHAR(30) NOT NULL DEFAULT 'manager',
            deadline TIMESTAMPTZ NOT NULL,
            recurrence VARCHAR(20) NOT NULL DEFAULT 'once',
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_campaigns_tenant ON access_campaigns(tenant_id)")

    # ------------------------------------------------------------------
    # access_review_tasks — itens individuais de revisão
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS access_review_tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            campaign_id UUID REFERENCES access_campaigns(id) ON DELETE CASCADE,
            reviewer_id UUID REFERENCES users(id) ON DELETE SET NULL,
            subject_user_id UUID REFERENCES ad_users(id) ON DELETE CASCADE,
            access_item_type VARCHAR(30) NOT NULL DEFAULT 'group',
            access_item_name VARCHAR(300) NOT NULL,
            decision VARCHAR(20) NOT NULL DEFAULT 'pending',
            decided_at TIMESTAMPTZ,
            comment TEXT,
            auto_revoked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_art_tenant ON access_review_tasks(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_art_reviewer ON access_review_tasks(reviewer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_art_decision ON access_review_tasks(tenant_id, decision)")

    # ------------------------------------------------------------------
    # jit_requests — solicitações de acesso temporário Just-In-Time
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS jit_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            requester_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            target_group_id UUID REFERENCES ad_groups(id) ON DELETE SET NULL,
            target_group_name VARCHAR(300) NOT NULL,
            reason TEXT NOT NULL,
            duration_hours INTEGER NOT NULL DEFAULT 4,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            approver_id UUID REFERENCES users(id) ON DELETE SET NULL,
            approved_at TIMESTAMPTZ,
            granted_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ,
            revoked_at TIMESTAMPTZ,
            revoked_by UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_jit_tenant ON jit_requests(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_jit_status ON jit_requests(tenant_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_jit_expires ON jit_requests(expires_at) WHERE status = 'active'")


def downgrade() -> None:
    for tbl in [
        "jit_requests", "access_review_tasks", "access_campaigns",
        "sod_violations", "sod_rules", "ad_group_memberships",
        "ad_groups", "ad_users", "identity_connectors",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {tbl}")
