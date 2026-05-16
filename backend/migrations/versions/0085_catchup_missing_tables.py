"""Catch-up: cria todas as tabelas ausentes dos migrations 0035-0073.

O banco foi configurado com uma versão antiga do codebase. Quando os arquivos de
migration foram substituídos, o alembic já estava em 0082 e não re-executou 0035-0073.
Este migration cria com IF NOT EXISTS tudo que estava faltando.

Revision ID: 0085
Revises: 0084
Create Date: 2026-05-16
"""
from alembic import op

revision = "0085"
down_revision = "0084"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # ALTER TABLE em tabelas que já existem
    # ------------------------------------------------------------------ #
    op.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS read_only_agent BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs(created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_action ON audit_logs(user_id, action)")

    op.execute("ALTER TABLE operations ADD COLUMN IF NOT EXISTS clarification_questions JSONB")
    op.execute("ALTER TABLE operations ADD COLUMN IF NOT EXISTS clarification_answers JSONB")
    op.execute("ALTER TABLE operations ADD COLUMN IF NOT EXISTS confidence_score FLOAT")

    # users: auth_source/ldap_dn/break_glass (0079 — pode ter falhado condicionalmente)
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_source VARCHAR(20) NOT NULL DEFAULT 'local'")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS ldap_dn TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS break_glass BOOLEAN NOT NULL DEFAULT FALSE")

    # ------------------------------------------------------------------ #
    # BATCH 1 — Tabelas com FK apenas para tenants/users/devices (pre-existentes)
    # ------------------------------------------------------------------ #

    # 0035 — identity_providers
    op.execute("""
        CREATE TABLE IF NOT EXISTS identity_providers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            provider_type VARCHAR(30) NOT NULL,
            encrypted_config TEXT NOT NULL DEFAULT '{}',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            last_sync_at TIMESTAMPTZ,
            last_sync_count INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_identity_providers_tenant ON identity_providers(tenant_id)")

    # 0035 — lifecycle_actions
    op.execute("""
        CREATE TABLE IF NOT EXISTS lifecycle_actions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            action_type VARCHAR(20) NOT NULL,
            target_username VARCHAR(256) NOT NULL,
            display_name VARCHAR(256),
            email VARCHAR(256),
            status VARCHAR(30) NOT NULL DEFAULT 'pending_discovery',
            requested_by UUID NOT NULL REFERENCES users(id),
            approved_by UUID REFERENCES users(id),
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            approved_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_lifecycle_actions_tenant ON lifecycle_actions(tenant_id)")

    # 0036 — external_connectors
    op.execute("""
        CREATE TABLE IF NOT EXISTS external_connectors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            connector_type VARCHAR(30) NOT NULL,
            encrypted_config TEXT NOT NULL DEFAULT '{}',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_external_connectors_tenant_id ON external_connectors(tenant_id)")

    # 0036 — onboarding_profiles
    op.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            ad_groups JSONB NOT NULL DEFAULT '[]',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_onboarding_profiles_tenant_id ON onboarding_profiles(tenant_id)")

    # 0037 — alert_channels
    op.execute("""
        CREATE TABLE IF NOT EXISTS alert_channels (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            channel_type VARCHAR(20) NOT NULL,
            encrypted_config TEXT NOT NULL DEFAULT '{}',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_channels_tenant_id ON alert_channels(tenant_id)")

    # 0037 — alert_rules
    op.execute("""
        CREATE TABLE IF NOT EXISTS alert_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            trigger VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL DEFAULT 'warning',
            channel_ids JSONB NOT NULL DEFAULT '[]',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_rules_tenant_id ON alert_rules(tenant_id)")

    # 0038/0056 — tenant_branding
    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_branding (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
            company_name VARCHAR(200),
            primary_color VARCHAR(7),
            logo_url VARCHAR(500),
            favicon_url VARCHAR(500),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_tenant_branding_tenant_id ON tenant_branding(tenant_id)")

    # 0038/0056 — api_keys (com plan da migration 0056)
    op.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            key_prefix VARCHAR(8) NOT NULL,
            key_hash VARCHAR(256) NOT NULL,
            permissions JSONB NOT NULL DEFAULT '[]',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            last_used_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            plan VARCHAR(20) NOT NULL DEFAULT 'starter'
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_keys_tenant_id ON api_keys(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_keys_key_prefix ON api_keys(key_prefix)")
    op.execute("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS plan VARCHAR(20) NOT NULL DEFAULT 'starter'")

    # 0039 — golden_bundles
    op.execute("""
        CREATE TABLE IF NOT EXISTS golden_bundles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            vendor VARCHAR(30) NOT NULL,
            variables JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_golden_bundles_tenant_id ON golden_bundles(tenant_id)")

    # 0040 — vm_hypervisors
    op.execute("""
        CREATE TABLE IF NOT EXISTS vm_hypervisors (
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
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_vm_hypervisors_tenant_id ON vm_hypervisors(tenant_id)")

    # 0041 — platform_config
    op.execute("""
        CREATE TABLE IF NOT EXISTS platform_config (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            key VARCHAR(100) NOT NULL UNIQUE,
            encrypted_value TEXT,
            description VARCHAR(500),
            is_sensitive BOOLEAN NOT NULL DEFAULT TRUE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_platform_config_key ON platform_config(key)")

    # 0043 — firmware tables (uses IF NOT EXISTS — pode já existir)
    op.execute("""
        CREATE TABLE IF NOT EXISTS device_firmware_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
            version VARCHAR(100) NOT NULL,
            vendor_label VARCHAR(100) NOT NULL,
            model VARCHAR(200),
            build VARCHAR(50),
            read_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            read_method VARCHAR(20) NOT NULL DEFAULT 'rest',
            raw_output TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_device_fw_versions_device ON device_firmware_versions(device_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS firmware_cves (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            cve_id VARCHAR(30) NOT NULL UNIQUE,
            vendor VARCHAR(50) NOT NULL,
            product VARCHAR(100) NOT NULL,
            affected_versions JSONB NOT NULL DEFAULT '{}',
            cvss_v3 FLOAT,
            cvss_v2 FLOAT,
            severity VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
            description TEXT NOT NULL DEFAULT '',
            published_at TIMESTAMPTZ,
            modified_at TIMESTAMPTZ,
            cpe_uri VARCHAR(500),
            nvd_url VARCHAR(300) NOT NULL DEFAULT '',
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_firmware_cves_vendor_product ON firmware_cves(vendor, product)")

    # 0046/0047 — assistant_folders (com min_role de 0047)
    op.execute("""
        CREATE TABLE IF NOT EXISTS assistant_folders (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            name TEXT NOT NULL,
            color VARCHAR(7) NOT NULL DEFAULT '#6366f1',
            is_team BOOLEAN NOT NULL DEFAULT FALSE,
            min_role VARCHAR(20) NOT NULL DEFAULT 'analyst_n1',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_assistant_folders_tenant ON assistant_folders(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_assistant_folders_tenant_user ON assistant_folders(tenant_id, user_id)")
    op.execute("ALTER TABLE assistant_folders ADD COLUMN IF NOT EXISTS min_role VARCHAR(20) NOT NULL DEFAULT 'analyst_n1'")

    # 0052 — ai_interactions
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_interactions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            operation_id UUID REFERENCES operations(id) ON DELETE SET NULL,
            session_id UUID,
            model VARCHAR(100) NOT NULL,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            prompt_hash VARCHAR(64),
            injection_score FLOAT DEFAULT 0,
            duration_ms INTEGER,
            sub_agent VARCHAR(50),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_interactions_tenant ON ai_interactions(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_interactions_op ON ai_interactions(operation_id) WHERE operation_id IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_interactions_month ON ai_interactions(tenant_id, created_at)")

    # 0052 — ai_token_usage
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_token_usage (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            month VARCHAR(7) NOT NULL,
            input_tokens BIGINT NOT NULL DEFAULT 0,
            output_tokens BIGINT NOT NULL DEFAULT 0,
            total_tokens BIGINT NOT NULL DEFAULT 0,
            cost_usd FLOAT DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, month)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_token_usage_tenant ON ai_token_usage(tenant_id)")

    # 0052 — orchestration_runs
    op.execute("""
        CREATE TABLE IF NOT EXISTS orchestration_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            operation_id UUID REFERENCES operations(id) ON DELETE SET NULL,
            user_query TEXT NOT NULL,
            agents_invoked JSONB NOT NULL DEFAULT '[]',
            result JSONB,
            status VARCHAR(30) NOT NULL DEFAULT 'running',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_orch_runs_tenant ON orchestration_runs(tenant_id)")

    # 0053 — identity_connectors (F36)
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

    # 0053 — sod_rules
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

    # 0053 — access_campaigns
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

    # 0054 — otp_requests
    op.execute("""
        CREATE TABLE IF NOT EXISTS otp_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            email VARCHAR(300) NOT NULL,
            otp_hash VARCHAR(128) NOT NULL,
            action VARCHAR(30) NOT NULL DEFAULT 'reset_password',
            used BOOLEAN NOT NULL DEFAULT false,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_otp_email ON otp_requests(email, used)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_otp_expires ON otp_requests(expires_at) WHERE used = false")

    # 0055/0060 — playbook_rules (com builder_state de 0060)
    op.execute("""
        CREATE TABLE IF NOT EXISTS playbook_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            trigger_type VARCHAR(50) NOT NULL,
            trigger_condition JSONB NOT NULL DEFAULT '{}',
            actions JSONB NOT NULL DEFAULT '[]',
            cooldown_minutes INTEGER NOT NULL DEFAULT 30,
            enabled BOOLEAN NOT NULL DEFAULT true,
            is_template BOOLEAN NOT NULL DEFAULT false,
            template_name VARCHAR(100),
            builder_state JSONB,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pb_rules_tenant ON playbook_rules(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pb_rules_trigger ON playbook_rules(tenant_id, trigger_type)")
    op.execute("ALTER TABLE playbook_rules ADD COLUMN IF NOT EXISTS builder_state JSONB")

    # 0055 — threat_indicators
    op.execute("""
        CREATE TABLE IF NOT EXISTS threat_indicators (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            ioc_type VARCHAR(20) NOT NULL,
            value VARCHAR(500) NOT NULL,
            source VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL DEFAULT 'medium',
            tags JSONB NOT NULL DEFAULT '[]',
            confidence FLOAT DEFAULT 0.8,
            last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (ioc_type, value, source)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ioc_type_val ON threat_indicators(ioc_type, value)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ioc_severity ON threat_indicators(severity)")

    # 0057 — siem_connectors
    op.execute("""
        CREATE TABLE IF NOT EXISTS siem_connectors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            siem_type VARCHAR(30) NOT NULL,
            base_url TEXT NOT NULL,
            config_encrypted TEXT,
            webhook_secret VARCHAR(64) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_event_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_siem_connectors_tenant_id ON siem_connectors(tenant_id)")

    # 0058 — cloud_accounts
    op.execute("""
        CREATE TABLE IF NOT EXISTS cloud_accounts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            provider VARCHAR(20) NOT NULL,
            credentials_encrypted TEXT,
            region VARCHAR(50),
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_sync_at TIMESTAMPTZ,
            last_sync_status VARCHAR(20),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_cloud_accounts_tenant_id ON cloud_accounts(tenant_id)")

    # 0059 — identity_posture_snapshots
    op.execute("""
        CREATE TABLE IF NOT EXISTS identity_posture_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            score INTEGER NOT NULL,
            mfa_pct FLOAT,
            admin_permanent_pct FLOAT,
            campaigns_on_time_pct FLOAT,
            sod_critical_open INTEGER,
            inactive_accounts INTEGER,
            details JSONB,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_identity_posture_tenant_id ON identity_posture_snapshots(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_identity_posture_computed_at ON identity_posture_snapshots(tenant_id, computed_at)")

    # 0059 — excessive_access_alerts
    op.execute("""
        CREATE TABLE IF NOT EXISTS excessive_access_alerts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID NOT NULL,
            rule_type VARCHAR(60) NOT NULL,
            details JSONB,
            severity VARCHAR(20) NOT NULL DEFAULT 'medium',
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_excessive_access_tenant_id ON excessive_access_alerts(tenant_id)")

    # 0059 — group_health_reports
    op.execute("""
        CREATE TABLE IF NOT EXISTS group_health_reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            group_id UUID NOT NULL,
            health_score INTEGER NOT NULL,
            issues JSONB,
            analyzed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_group_health_tenant_id ON group_health_reports(tenant_id)")

    # 0059 — role_profiles
    op.execute("""
        CREATE TABLE IF NOT EXISTS role_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            job_title VARCHAR(200) NOT NULL,
            department VARCHAR(200),
            standard_groups JSONB,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_role_profiles_tenant_id ON role_profiles(tenant_id)")

    # 0061 — compliance_packs
    op.execute("""
        CREATE TABLE IF NOT EXISTS compliance_packs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(200) NOT NULL,
            framework VARCHAR(50) NOT NULL,
            version VARCHAR(20),
            description TEXT,
            is_builtin BOOLEAN NOT NULL DEFAULT true,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # 0061 — bcdr_plans
    op.execute("""
        CREATE TABLE IF NOT EXISTS bcdr_plans (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            rto_hours INTEGER NOT NULL DEFAULT 4,
            rpo_hours INTEGER NOT NULL DEFAULT 1,
            scope TEXT,
            contacts JSONB,
            recovery_steps JSONB,
            last_test_at TIMESTAMPTZ,
            last_test_result VARCHAR(20),
            last_test_notes TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_bcdr_plans_tenant_id ON bcdr_plans(tenant_id)")

    # 0061 — sla_configs
    op.execute("""
        CREATE TABLE IF NOT EXISTS sla_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            tier_name VARCHAR(50) NOT NULL,
            response_minutes INTEGER NOT NULL DEFAULT 60,
            resolution_hours INTEGER NOT NULL DEFAULT 8,
            escalation_hours INTEGER,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, tier_name)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_sla_configs_tenant_id ON sla_configs(tenant_id)")

    # 0062 — maintenance_windows
    op.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_windows (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            starts_at TIMESTAMPTZ NOT NULL,
            ends_at TIMESTAMPTZ NOT NULL,
            recurrence VARCHAR(20) NOT NULL DEFAULT 'once',
            recurrence_day INTEGER,
            affected_devices JSONB,
            block_ai_operations BOOLEAN NOT NULL DEFAULT true,
            block_bulk_jobs BOOLEAN NOT NULL DEFAULT true,
            created_by UUID,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_maintenance_windows_tenant_id ON maintenance_windows(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_maintenance_windows_tenant_active ON maintenance_windows(tenant_id, is_active)")

    # 0062 — approval_requests
    op.execute("""
        CREATE TABLE IF NOT EXISTS approval_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            title VARCHAR(300) NOT NULL,
            description TEXT,
            operation_context JSONB,
            risk_level VARCHAR(20) NOT NULL DEFAULT 'high',
            requester_id UUID,
            requester_note TEXT,
            first_approver_id UUID,
            first_approved_at TIMESTAMPTZ,
            second_approver_id UUID,
            second_approved_at TIMESTAMPTZ,
            rejection_reason TEXT,
            rejected_by UUID,
            rejected_at TIMESTAMPTZ,
            status VARCHAR(20) NOT NULL DEFAULT 'pending_first',
            requires_two_approvals BOOLEAN NOT NULL DEFAULT true,
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_approval_requests_tenant_id ON approval_requests(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_approval_requests_tenant_status ON approval_requests(tenant_id, status)")

    # 0062 — erasure_requests
    op.execute("""
        CREATE TABLE IF NOT EXISTS erasure_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            requested_by UUID,
            target_user_email VARCHAR(255) NOT NULL,
            reason TEXT,
            legal_basis VARCHAR(100),
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            rejection_reason TEXT,
            affected_tables JSONB,
            audit_summary JSONB,
            approved_by UUID,
            approved_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_erasure_requests_tenant_id ON erasure_requests(tenant_id)")

    # 0064 — vault_configs
    op.execute("""
        CREATE TABLE IF NOT EXISTS vault_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            name VARCHAR(200) NOT NULL,
            vault_url VARCHAR(500) NOT NULL,
            auth_method VARCHAR(30) NOT NULL DEFAULT 'token',
            token_encrypted TEXT,
            role_id VARCHAR(200),
            secret_id_encrypted TEXT,
            default_mount VARCHAR(100) NOT NULL DEFAULT 'secret',
            namespace VARCHAR(200),
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_verified_at TIMESTAMPTZ,
            last_verified_ok BOOLEAN,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_vault_configs_tenant_id ON vault_configs(tenant_id)")

    # 0064 — opa_policies
    op.execute("""
        CREATE TABLE IF NOT EXISTS opa_policies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            package_name VARCHAR(200) NOT NULL DEFAULT 'eternity',
            rego_source TEXT NOT NULL,
            category VARCHAR(50),
            is_active BOOLEAN NOT NULL DEFAULT true,
            version INTEGER NOT NULL DEFAULT 1,
            created_by UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_opa_policies_tenant_id ON opa_policies(tenant_id)")

    # 0064 — security_profiles
    op.execute("""
        CREATE TABLE IF NOT EXISTS security_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            name VARCHAR(200) NOT NULL,
            profile_type VARCHAR(30) NOT NULL DEFAULT 'hardening',
            controls JSONB,
            applied_at TIMESTAMPTZ,
            applied_by UUID,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_security_profiles_tenant_id ON security_profiles(tenant_id)")

    # 0064 — pentest_schedules
    op.execute("""
        CREATE TABLE IF NOT EXISTS pentest_schedules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            title VARCHAR(200) NOT NULL,
            scope TEXT,
            pentest_type VARCHAR(30) NOT NULL DEFAULT 'external',
            vendor VARCHAR(200),
            scheduled_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            status VARCHAR(20) NOT NULL DEFAULT 'planned',
            findings_critical INTEGER NOT NULL DEFAULT 0,
            findings_high INTEGER NOT NULL DEFAULT 0,
            findings_medium INTEGER NOT NULL DEFAULT 0,
            findings_low INTEGER NOT NULL DEFAULT 0,
            report_url VARCHAR(500),
            remediation_deadline TIMESTAMPTZ,
            created_by UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pentest_schedules_tenant_id ON pentest_schedules(tenant_id)")

    # 0065 — edge_agents
    op.execute("""
        CREATE TABLE IF NOT EXISTS edge_agents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            name VARCHAR(200) NOT NULL,
            token_hash VARCHAR(64) NOT NULL UNIQUE,
            device_ids JSONB,
            version VARCHAR(30),
            status VARCHAR(20) NOT NULL DEFAULT 'offline',
            last_seen TIMESTAMPTZ,
            ip_address VARCHAR(50),
            notes TEXT,
            created_by UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_edge_agents_tenant_id ON edge_agents(tenant_id)")

    # 0065/0079 — sso_configs (com extra_config de 0079)
    op.execute("""
        CREATE TABLE IF NOT EXISTS sso_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL UNIQUE,
            provider VARCHAR(30) NOT NULL DEFAULT 'azure_ad',
            client_id VARCHAR(200) NOT NULL,
            client_secret_encrypted TEXT,
            discovery_url VARCHAR(500) NOT NULL,
            group_claim VARCHAR(100) DEFAULT 'groups',
            group_mapping JSONB,
            sso_required BOOLEAN NOT NULL DEFAULT false,
            is_active BOOLEAN NOT NULL DEFAULT true,
            extra_config JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_sso_configs_tenant_id ON sso_configs(tenant_id)")
    op.execute("ALTER TABLE sso_configs ADD COLUMN IF NOT EXISTS extra_config JSONB")

    # 0065 — marketplace_plugins
    op.execute("""
        CREATE TABLE IF NOT EXISTS marketplace_plugins (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(200) NOT NULL UNIQUE,
            slug VARCHAR(100) NOT NULL UNIQUE,
            version VARCHAR(30) NOT NULL,
            author_tenant_id UUID,
            category VARCHAR(50) NOT NULL DEFAULT 'connector',
            description TEXT,
            package_url VARCHAR(500),
            signature VARCHAR(200),
            approved_at TIMESTAMPTZ,
            approved_by UUID,
            is_builtin BOOLEAN NOT NULL DEFAULT false,
            download_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # 0065 — rbac_custom_roles
    op.execute("""
        CREATE TABLE IF NOT EXISTS rbac_custom_roles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            permissions JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, name)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_rbac_custom_roles_tenant_id ON rbac_custom_roles(tenant_id)")

    # 0066 — billing_plans
    op.execute("""
        CREATE TABLE IF NOT EXISTS billing_plans (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(50) NOT NULL UNIQUE,
            slug VARCHAR(30) NOT NULL UNIQUE,
            monthly_price_brl NUMERIC(10,2) NOT NULL DEFAULT 0,
            max_devices INTEGER,
            max_users INTEGER,
            ai_token_quota INTEGER,
            sla_target_pct NUMERIC(5,2),
            features JSONB,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # 0066 — help_articles
    op.execute("""
        CREATE TABLE IF NOT EXISTS help_articles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(300) NOT NULL,
            slug VARCHAR(200) NOT NULL UNIQUE,
            category VARCHAR(50) NOT NULL DEFAULT 'general',
            persona VARCHAR(30),
            content_md TEXT NOT NULL,
            is_published BOOLEAN NOT NULL DEFAULT false,
            view_count INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_by UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # 0066 — user_preferences
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL UNIQUE,
            language VARCHAR(10) NOT NULL DEFAULT 'pt-BR',
            timezone VARCHAR(50) NOT NULL DEFAULT 'America/Sao_Paulo',
            theme VARCHAR(20) NOT NULL DEFAULT 'dark',
            notifications_enabled BOOLEAN NOT NULL DEFAULT true,
            onboarding_step INTEGER NOT NULL DEFAULT 0,
            onboarding_completed BOOLEAN NOT NULL DEFAULT false,
            extra JSONB,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # 0068 — rmm_integrations
    op.execute("""
        CREATE TABLE IF NOT EXISTS rmm_integrations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            rmm_type VARCHAR(30) NOT NULL,
            base_url TEXT NOT NULL,
            config_encrypted TEXT,
            verify_ssl BOOLEAN NOT NULL DEFAULT true,
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_sync_at TIMESTAMPTZ,
            last_sync_status VARCHAR(20),
            last_sync_message TEXT,
            agent_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_rmm_integrations_tenant_id ON rmm_integrations(tenant_id)")

    # 0069 — sso_role_mappings
    op.execute("""
        CREATE TABLE IF NOT EXISTS sso_role_mappings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sso_config_id UUID NOT NULL,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            external_group VARCHAR(300) NOT NULL,
            platform_role VARCHAR(50) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (sso_config_id, external_group)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_sso_role_mappings_sso_config_id ON sso_role_mappings(sso_config_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sso_role_mappings_tenant_id ON sso_role_mappings(tenant_id)")

    # 0070 — file_share_configs
    op.execute("""
        CREATE TABLE IF NOT EXISTS file_share_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            server_hostname VARCHAR(200) NOT NULL,
            unc_root VARCHAR(500) NOT NULL,
            edge_agent_id UUID,
            config_encrypted TEXT,
            scan_depth INTEGER NOT NULL DEFAULT 2,
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_scan_at TIMESTAMPTZ,
            last_scan_status VARCHAR(20),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_file_share_configs_tenant_id ON file_share_configs(tenant_id)")

    # 0071 — siem_syslog_configs
    op.execute("""
        CREATE TABLE IF NOT EXISTS siem_syslog_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            target_host VARCHAR(300) NOT NULL,
            target_port INTEGER NOT NULL DEFAULT 514,
            protocol VARCHAR(10) NOT NULL DEFAULT 'tcp',
            tls_enabled BOOLEAN NOT NULL DEFAULT false,
            tls_verify BOOLEAN NOT NULL DEFAULT true,
            facility INTEGER NOT NULL DEFAULT 1,
            min_severity VARCHAR(20) NOT NULL DEFAULT 'low',
            event_types JSONB,
            enabled BOOLEAN NOT NULL DEFAULT true,
            last_forward_at TIMESTAMPTZ,
            events_forwarded INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_siem_syslog_configs_tenant_id ON siem_syslog_configs(tenant_id)")

    # 0067 — dlp_configs
    op.execute("""
        CREATE TABLE IF NOT EXISTS dlp_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
            enabled BOOLEAN NOT NULL DEFAULT true,
            compliance_mode BOOLEAN NOT NULL DEFAULT false,
            incident_threshold_count INTEGER NOT NULL DEFAULT 5,
            incident_threshold_hours INTEGER NOT NULL DEFAULT 24,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS dlp_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            rule_key VARCHAR(64) NOT NULL,
            rule_name VARCHAR(100) NOT NULL,
            description VARCHAR(255),
            category VARCHAR(32) NOT NULL,
            action VARCHAR(8) NOT NULL DEFAULT 'block',
            is_enabled BOOLEAN NOT NULL DEFAULT true,
            is_builtin BOOLEAN NOT NULL DEFAULT true,
            pattern TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_dlp_rules_tenant_key UNIQUE (tenant_id, rule_key)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_dlp_rules_tenant_id ON dlp_rules(tenant_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS dlp_incidents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            pii_type VARCHAR(64) NOT NULL,
            action_taken VARCHAR(8) NOT NULL,
            source VARCHAR(32) NOT NULL DEFAULT 'chat',
            ip_address VARCHAR(45),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_dlp_incidents_tenant_id ON dlp_incidents(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_dlp_incidents_created_at ON dlp_incidents(created_at)")

    # 0073 — stripe_webhook_events
    op.execute("""
        CREATE TABLE IF NOT EXISTS stripe_webhook_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            stripe_event_id VARCHAR(100) NOT NULL UNIQUE,
            event_type VARCHAR(100) NOT NULL,
            tenant_id UUID,
            payload JSONB,
            processed BOOLEAN NOT NULL DEFAULT false,
            error TEXT,
            received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            processed_at TIMESTAMPTZ
        )
    """)

    # ------------------------------------------------------------------ #
    # BATCH 2 — Tabelas com FK para tabelas do BATCH 1
    # ------------------------------------------------------------------ #

    # 0045/0046/0051 — assistant_sessions (com TODOS os campos)
    op.execute("""
        CREATE TABLE IF NOT EXISTS assistant_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT,
            model_used VARCHAR(100) NOT NULL DEFAULT 'claude-sonnet-4-6',
            message_count INTEGER NOT NULL DEFAULT 0,
            last_hash VARCHAR(64),
            folder_id UUID REFERENCES assistant_folders(id) ON DELETE SET NULL,
            is_shared BOOLEAN NOT NULL DEFAULT FALSE,
            shared_by UUID REFERENCES users(id) ON DELETE SET NULL,
            pinned BOOLEAN NOT NULL DEFAULT FALSE,
            glpi_ticket_id INTEGER,
            glpi_integration_id UUID,
            glpi_itemtype VARCHAR(50),
            glpi_ticket_title TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_assistant_sessions_tenant_user ON assistant_sessions(tenant_id, user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_assistant_sessions_glpi_ticket_id ON assistant_sessions(glpi_ticket_id)")
    op.execute("ALTER TABLE assistant_sessions ADD COLUMN IF NOT EXISTS folder_id UUID REFERENCES assistant_folders(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE assistant_sessions ADD COLUMN IF NOT EXISTS is_shared BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE assistant_sessions ADD COLUMN IF NOT EXISTS shared_by UUID REFERENCES users(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE assistant_sessions ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE assistant_sessions ADD COLUMN IF NOT EXISTS glpi_ticket_id INTEGER")
    op.execute("ALTER TABLE assistant_sessions ADD COLUMN IF NOT EXISTS glpi_integration_id UUID")
    op.execute("ALTER TABLE assistant_sessions ADD COLUMN IF NOT EXISTS glpi_itemtype VARCHAR(50)")
    op.execute("ALTER TABLE assistant_sessions ADD COLUMN IF NOT EXISTS glpi_ticket_title TEXT")

    # 0035 — identity_users
    op.execute("""
        CREATE TABLE IF NOT EXISTS identity_users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            provider_id UUID NOT NULL REFERENCES identity_providers(id) ON DELETE CASCADE,
            external_id VARCHAR(256) NOT NULL,
            username VARCHAR(256) NOT NULL,
            display_name VARCHAR(256),
            email VARCHAR(256),
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            department VARCHAR(256),
            job_title VARCHAR(256),
            last_sign_in_raw VARCHAR(64),
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_identity_users_tenant ON identity_users(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_identity_users_provider ON identity_users(provider_id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_identity_users_ext ON identity_users(provider_id, external_id)")

    # 0035 — lifecycle_tasks
    op.execute("""
        CREATE TABLE IF NOT EXISTS lifecycle_tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            action_id UUID NOT NULL REFERENCES lifecycle_actions(id) ON DELETE CASCADE,
            system_type VARCHAR(30) NOT NULL,
            system_id VARCHAR(36),
            system_name VARCHAR(256) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            result TEXT,
            error TEXT,
            executed_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_lifecycle_tasks_action ON lifecycle_tasks(action_id)")

    # 0036 — onboarding_profile_systems
    op.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_profile_systems (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            profile_id UUID NOT NULL REFERENCES onboarding_profiles(id) ON DELETE CASCADE,
            system_type VARCHAR(30) NOT NULL,
            system_id VARCHAR(36),
            system_name VARCHAR(256) NOT NULL,
            config JSONB NOT NULL DEFAULT '{}'
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_onboarding_profile_systems_profile_id ON onboarding_profile_systems(profile_id)")

    # 0037 — alert_events
    op.execute("""
        CREATE TABLE IF NOT EXISTS alert_events (
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
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_events_tenant_id ON alert_events(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_events_created_at ON alert_events(created_at DESC)")

    # 0039 — bundle_sections
    op.execute("""
        CREATE TABLE IF NOT EXISTS bundle_sections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bundle_id UUID NOT NULL REFERENCES golden_bundles(id) ON DELETE CASCADE,
            section_type VARCHAR(50) NOT NULL,
            template_id UUID REFERENCES golden_templates(id) ON DELETE SET NULL,
            rest_payload_template TEXT,
            apply_strategy VARCHAR(20) NOT NULL DEFAULT 'rest_api',
            apply_order INTEGER NOT NULL DEFAULT 0,
            rollback_strategy VARCHAR(30) NOT NULL DEFAULT 'none'
        )
    """)

    # 0039 — bundle_applies
    op.execute("""
        CREATE TABLE IF NOT EXISTS bundle_applies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bundle_id UUID NOT NULL REFERENCES golden_bundles(id) ON DELETE CASCADE,
            device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
            status VARCHAR(20) NOT NULL DEFAULT 'applying',
            variables_used JSONB,
            section_results JSONB,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_bundle_applies_bundle_id ON bundle_applies(bundle_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bundle_applies_device_id ON bundle_applies(device_id)")

    # 0040 — vm_inventory
    op.execute("""
        CREATE TABLE IF NOT EXISTS vm_inventory (
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
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_vm_inventory_hypervisor_id ON vm_inventory(hypervisor_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vm_inventory_tenant_id ON vm_inventory(tenant_id)")

    # 0040 — migration_runbooks
    op.execute("""
        CREATE TABLE IF NOT EXISTS migration_runbooks (
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
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_migration_runbooks_tenant_id ON migration_runbooks(tenant_id)")

    # 0053 — ad_users
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

    # 0053 — ad_groups
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

    # 0055 — playbook_executions
    op.execute("""
        CREATE TABLE IF NOT EXISTS playbook_executions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            rule_id UUID NOT NULL REFERENCES playbook_rules(id) ON DELETE CASCADE,
            triggered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            trigger_context JSONB NOT NULL DEFAULT '{}',
            actions_taken JSONB NOT NULL DEFAULT '[]',
            status VARCHAR(20) NOT NULL DEFAULT 'running',
            resolved_at TIMESTAMPTZ,
            error_message TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pb_exec_tenant ON playbook_executions(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pb_exec_rule ON playbook_executions(rule_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pb_exec_status ON playbook_executions(tenant_id, status)")

    # 0057 — siem_alerts
    op.execute("""
        CREATE TABLE IF NOT EXISTS siem_alerts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            connector_id UUID NOT NULL REFERENCES siem_connectors(id) ON DELETE CASCADE,
            source_rule_id TEXT,
            severity VARCHAR(20) NOT NULL DEFAULT 'medium',
            title TEXT NOT NULL,
            description TEXT,
            affected_host TEXT,
            source_ip TEXT,
            raw_payload JSONB,
            normalized_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            playbook_triggered BOOLEAN NOT NULL DEFAULT false,
            playbook_execution_id UUID
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_siem_alerts_tenant_id ON siem_alerts(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_siem_alerts_tenant_normalized_at ON siem_alerts(tenant_id, normalized_at)")

    # 0058 — cloud_security_findings
    op.execute("""
        CREATE TABLE IF NOT EXISTS cloud_security_findings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id UUID NOT NULL REFERENCES cloud_accounts(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            resource_type VARCHAR(50) NOT NULL,
            resource_id TEXT NOT NULL,
            resource_name TEXT,
            check_id VARCHAR(80) NOT NULL,
            check_title TEXT NOT NULL,
            severity VARCHAR(20) NOT NULL DEFAULT 'medium',
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            details JSONB,
            detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            resolved_at TIMESTAMPTZ,
            accepted_by UUID,
            accepted_reason TEXT,
            UNIQUE (account_id, resource_id, check_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_cloud_findings_tenant_id ON cloud_security_findings(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cloud_findings_account_id ON cloud_security_findings(account_id)")

    # 0058 — cloud_resources
    op.execute("""
        CREATE TABLE IF NOT EXISTS cloud_resources (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id UUID NOT NULL REFERENCES cloud_accounts(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            resource_type VARCHAR(50) NOT NULL,
            resource_id TEXT NOT NULL,
            resource_name TEXT,
            region VARCHAR(50),
            rules JSONB,
            tags JSONB,
            risk_score INTEGER,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_cloud_resources_tenant_id ON cloud_resources(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cloud_resources_account_id ON cloud_resources(account_id)")

    # 0061 — compliance_pack_controls
    op.execute("""
        CREATE TABLE IF NOT EXISTS compliance_pack_controls (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            pack_id UUID NOT NULL REFERENCES compliance_packs(id) ON DELETE CASCADE,
            control_id VARCHAR(50) NOT NULL,
            title VARCHAR(300) NOT NULL,
            description TEXT,
            category VARCHAR(100),
            severity VARCHAR(20) NOT NULL DEFAULT 'medium',
            verification_type VARCHAR(20) NOT NULL DEFAULT 'manual',
            evidence_hint TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_compliance_pack_controls_pack_id ON compliance_pack_controls(pack_id)")

    # 0061 — compliance_pack_assessments
    op.execute("""
        CREATE TABLE IF NOT EXISTS compliance_pack_assessments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            pack_id UUID REFERENCES compliance_packs(id) ON DELETE SET NULL,
            pack_name VARCHAR(200) NOT NULL,
            name VARCHAR(200) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'in_progress',
            overall_score FLOAT,
            compliant_count INTEGER NOT NULL DEFAULT 0,
            partial_count INTEGER NOT NULL DEFAULT 0,
            non_compliant_count INTEGER NOT NULL DEFAULT 0,
            total_controls INTEGER NOT NULL DEFAULT 0,
            findings JSONB,
            created_by UUID,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_compliance_assessments_tenant_id ON compliance_pack_assessments(tenant_id)")

    # 0064 — vault_secret_refs
    op.execute("""
        CREATE TABLE IF NOT EXISTS vault_secret_refs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            vault_config_id UUID NOT NULL REFERENCES vault_configs(id) ON DELETE CASCADE,
            alias VARCHAR(200) NOT NULL,
            vault_path VARCHAR(500) NOT NULL,
            vault_key VARCHAR(200) NOT NULL DEFAULT 'value',
            description TEXT,
            category VARCHAR(50),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, alias)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_vault_secret_refs_tenant_id ON vault_secret_refs(tenant_id)")

    # 0064 — opa_evaluations
    op.execute("""
        CREATE TABLE IF NOT EXISTS opa_evaluations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            policy_id UUID REFERENCES opa_policies(id) ON DELETE SET NULL,
            policy_name VARCHAR(200) NOT NULL,
            input_data JSONB,
            result JSONB,
            allowed BOOLEAN,
            evaluated_by UUID,
            evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_opa_evaluations_tenant_id ON opa_evaluations(tenant_id)")

    # 0065 — tenant_plugins
    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_plugins (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            plugin_id UUID NOT NULL REFERENCES marketplace_plugins(id) ON DELETE CASCADE,
            installed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            installed_by UUID,
            config JSONB,
            UNIQUE (tenant_id, plugin_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_tenant_plugins_tenant_id ON tenant_plugins(tenant_id)")

    # 0065 — rbac_role_assignments
    op.execute("""
        CREATE TABLE IF NOT EXISTS rbac_role_assignments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            user_id UUID NOT NULL,
            role_id UUID NOT NULL REFERENCES rbac_custom_roles(id) ON DELETE CASCADE,
            assigned_by UUID,
            assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, user_id, role_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_rbac_role_assignments_tenant_id ON rbac_role_assignments(tenant_id)")

    # 0066/0073 — billing_subscriptions (com stripe_price_id de 0073)
    op.execute("""
        CREATE TABLE IF NOT EXISTS billing_subscriptions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL UNIQUE,
            plan_id UUID NOT NULL REFERENCES billing_plans(id),
            stripe_customer_id VARCHAR(200),
            stripe_subscription_id VARCHAR(200),
            stripe_price_id VARCHAR(100),
            status VARCHAR(30) NOT NULL DEFAULT 'active',
            current_period_start TIMESTAMPTZ,
            current_period_end TIMESTAMPTZ,
            cancel_at_period_end BOOLEAN NOT NULL DEFAULT false,
            trial_end TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_billing_subscriptions_tenant_id ON billing_subscriptions(tenant_id)")
    op.execute("ALTER TABLE billing_subscriptions ADD COLUMN IF NOT EXISTS stripe_price_id VARCHAR(100)")

    # 0066 — onboarding_checklists
    op.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_checklists (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            user_id UUID NOT NULL,
            step_add_device BOOLEAN NOT NULL DEFAULT false,
            step_run_snapshot BOOLEAN NOT NULL DEFAULT false,
            step_ask_agent BOOLEAN NOT NULL DEFAULT false,
            step_configure_alert BOOLEAN NOT NULL DEFAULT false,
            completed BOOLEAN NOT NULL DEFAULT false,
            skipped BOOLEAN NOT NULL DEFAULT false,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, user_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_onboarding_checklists_tenant_id ON onboarding_checklists(tenant_id)")

    # 0068 — rmm_agents
    op.execute("""
        CREATE TABLE IF NOT EXISTS rmm_agents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            integration_id UUID NOT NULL REFERENCES rmm_integrations(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            external_id VARCHAR(200) NOT NULL,
            hostname VARCHAR(200) NOT NULL,
            os_name TEXT,
            ip_address VARCHAR(50),
            status VARCHAR(20) NOT NULL DEFAULT 'unknown',
            last_seen TIMESTAMPTZ,
            patches_pending INTEGER,
            alerts_count INTEGER NOT NULL DEFAULT 0,
            raw_data JSONB,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (integration_id, external_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_rmm_agents_integration_id ON rmm_agents(integration_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rmm_agents_tenant_id ON rmm_agents(tenant_id)")

    # 0070 — file_share_shares
    op.execute("""
        CREATE TABLE IF NOT EXISTS file_share_shares (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            config_id UUID NOT NULL REFERENCES file_share_configs(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            share_name VARCHAR(200) NOT NULL,
            unc_path VARCHAR(500) NOT NULL,
            description TEXT,
            abe_enabled BOOLEAN,
            health_status VARCHAR(20) NOT NULL DEFAULT 'unknown',
            health_issues JSONB,
            acl_count INTEGER NOT NULL DEFAULT 0,
            scanned_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_file_share_shares_config_id ON file_share_shares(config_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_file_share_shares_tenant_id ON file_share_shares(tenant_id)")

    # 0072 — glpi_widget_tokens (glpi_integrations exists from migration 0021)
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

    # 0043 — device_firmware_vulnerabilities
    op.execute("""
        CREATE TABLE IF NOT EXISTS device_firmware_vulnerabilities (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
            cve_id VARCHAR(30) NOT NULL,
            device_version VARCHAR(100) NOT NULL,
            detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            accepted_by UUID,
            accepted_reason TEXT,
            patched_at TIMESTAMPTZ,
            UNIQUE(device_id, cve_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_device_fw_vulns_device_status ON device_firmware_vulnerabilities(device_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_device_fw_vulns_cve ON device_firmware_vulnerabilities(cve_id)")

    # ------------------------------------------------------------------ #
    # BATCH 3 — Tabelas com FK para tabelas do BATCH 2
    # ------------------------------------------------------------------ #

    # 0045/0048/0049/0050 — assistant_messages
    op.execute("""
        CREATE TABLE IF NOT EXISTS assistant_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL REFERENCES assistant_sessions(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            model VARCHAR(100),
            input_tokens INTEGER,
            output_tokens INTEGER,
            rag_context_used BOOLEAN NOT NULL DEFAULT FALSE,
            message_hash VARCHAR(64) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_assistant_messages_session ON assistant_messages(session_id, created_at)")

    # 0048/0049/0050 — assistant_doc_drafts (com similar_docs e doc_type)
    op.execute("""
        CREATE TABLE IF NOT EXISTS assistant_doc_drafts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL REFERENCES assistant_sessions(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            doc_type VARCHAR(20) NOT NULL DEFAULT 'knowledge',
            review_deadline TIMESTAMPTZ,
            sanitizer_warnings JSONB NOT NULL DEFAULT '[]',
            similar_docs JSONB NOT NULL DEFAULT '[]',
            bookstack_page_id INTEGER,
            bookstack_page_url TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_doc_drafts_tenant_status ON assistant_doc_drafts(tenant_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_doc_drafts_session ON assistant_doc_drafts(session_id)")
    op.execute("ALTER TABLE assistant_doc_drafts ADD COLUMN IF NOT EXISTS similar_docs JSONB NOT NULL DEFAULT '[]'")
    op.execute("ALTER TABLE assistant_doc_drafts ADD COLUMN IF NOT EXISTS doc_type VARCHAR(20) NOT NULL DEFAULT 'knowledge'")

    # 0053 — jit_requests
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

    # 0066/0073 — billing_invoices (com stripe_payment_intent e payment_url de 0073)
    op.execute("""
        CREATE TABLE IF NOT EXISTS billing_invoices (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            subscription_id UUID REFERENCES billing_subscriptions(id) ON DELETE SET NULL,
            stripe_invoice_id VARCHAR(200) UNIQUE,
            stripe_payment_intent VARCHAR(100),
            payment_url TEXT,
            amount_brl NUMERIC(10,2) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            period_start TIMESTAMPTZ,
            period_end TIMESTAMPTZ,
            paid_at TIMESTAMPTZ,
            due_date TIMESTAMPTZ,
            invoice_pdf_url VARCHAR(500),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_billing_invoices_tenant_id ON billing_invoices(tenant_id)")
    op.execute("ALTER TABLE billing_invoices ADD COLUMN IF NOT EXISTS stripe_payment_intent VARCHAR(100)")
    op.execute("ALTER TABLE billing_invoices ADD COLUMN IF NOT EXISTS payment_url TEXT")

    # 0070 — file_share_acl_entries
    op.execute("""
        CREATE TABLE IF NOT EXISTS file_share_acl_entries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            share_id UUID NOT NULL REFERENCES file_share_shares(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            folder_path TEXT NOT NULL,
            principal_name VARCHAR(300) NOT NULL,
            principal_type VARCHAR(20) NOT NULL DEFAULT 'unknown',
            permission_type VARCHAR(50) NOT NULL,
            inherited BOOLEAN NOT NULL DEFAULT false,
            is_deny BOOLEAN NOT NULL DEFAULT false,
            depth INTEGER NOT NULL DEFAULT 0,
            scanned_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_file_share_acl_entries_share_id ON file_share_acl_entries(share_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_file_share_acl_entries_tenant_id ON file_share_acl_entries(tenant_id)")

    # ------------------------------------------------------------------ #
    # BATCH 4 — Tabelas com FK para tabelas do BATCH 3
    # ------------------------------------------------------------------ #

    # 0053 — sod_violations
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

    # 0053 — access_review_tasks
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

    # 0053 — ad_group_memberships
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

    # ------------------------------------------------------------------ #
    # Adiciona FK em devices.edge_agent_id se edge_agents agora existe
    # ------------------------------------------------------------------ #
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = 'devices'
                  AND tc.constraint_type = 'FOREIGN KEY'
                  AND kcu.column_name = 'edge_agent_id'
            ) THEN
                ALTER TABLE devices
                ADD CONSTRAINT fk_devices_edge_agent_id
                FOREIGN KEY (edge_agent_id) REFERENCES edge_agents(id) ON DELETE SET NULL;
            END IF;
        END $$
    """)


def downgrade() -> None:
    # Drop in reverse dependency order
    op.execute("ALTER TABLE devices DROP CONSTRAINT IF EXISTS fk_devices_edge_agent_id")
    for tbl in [
        "ad_group_memberships", "access_review_tasks", "sod_violations",
        "billing_invoices", "file_share_acl_entries",
        "assistant_doc_drafts", "assistant_messages",
        "jit_requests",
        "rmm_agents", "file_share_shares", "glpi_widget_tokens",
        "device_firmware_vulnerabilities",
        "onboarding_checklists", "rbac_role_assignments", "tenant_plugins",
        "opa_evaluations", "vault_secret_refs",
        "compliance_pack_assessments", "compliance_pack_controls",
        "cloud_resources", "cloud_security_findings",
        "siem_alerts", "playbook_executions",
        "ad_groups", "ad_users",
        "migration_runbooks", "vm_inventory",
        "bundle_applies", "bundle_sections",
        "alert_events",
        "onboarding_profile_systems",
        "lifecycle_tasks", "identity_users",
        "assistant_sessions",
        "billing_subscriptions", "billing_plans",
        "rbac_custom_roles", "marketplace_plugins",
        "sso_configs", "edge_agents",
        "pentest_schedules", "security_profiles",
        "opa_policies", "vault_configs",
        "erasure_requests", "approval_requests", "maintenance_windows",
        "sla_configs", "bcdr_plans",
        "compliance_packs",
        "role_profiles", "group_health_reports",
        "excessive_access_alerts", "identity_posture_snapshots",
        "cloud_accounts",
        "siem_connectors",
        "threat_indicators", "playbook_executions", "playbook_rules",
        "otp_requests",
        "access_campaigns", "sod_rules",
        "identity_connectors",
        "orchestration_runs", "ai_token_usage", "ai_interactions",
        "assistant_folders",
        "platform_config",
        "vm_hypervisors",
        "golden_bundles",
        "api_keys", "tenant_branding",
        "alert_rules", "alert_channels",
        "onboarding_profiles", "external_connectors",
        "lifecycle_actions",
        "identity_providers",
        "device_firmware_vulnerabilities", "firmware_cves", "device_firmware_versions",
        "rmm_integrations", "sso_role_mappings",
        "file_share_configs", "siem_syslog_configs",
        "dlp_incidents", "dlp_rules", "dlp_configs",
        "stripe_webhook_events",
        "glpi_widget_tokens",
        "user_preferences", "help_articles",
        "onboarding_checklists",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")
