"""Fase 21: identity_providers, identity_users, lifecycle_actions, lifecycle_tasks

Revision ID: 0035
Revises: 0034
Create Date: 2026-05-08
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text("""
        CREATE TABLE identity_providers (
            id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name            VARCHAR(100) NOT NULL,
            provider_type   VARCHAR(30)  NOT NULL,
            encrypted_config TEXT        NOT NULL DEFAULT '{}',
            is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
            last_sync_at    TIMESTAMPTZ,
            last_sync_count INTEGER,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_identity_providers_tenant ON identity_providers(tenant_id);

        CREATE TABLE identity_users (
            id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            provider_id     UUID         NOT NULL REFERENCES identity_providers(id) ON DELETE CASCADE,
            external_id     VARCHAR(256) NOT NULL,
            username        VARCHAR(256) NOT NULL,
            display_name    VARCHAR(256),
            email           VARCHAR(256),
            is_enabled      BOOLEAN      NOT NULL DEFAULT TRUE,
            department      VARCHAR(256),
            job_title       VARCHAR(256),
            last_sign_in_raw VARCHAR(64),
            synced_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_identity_users_tenant  ON identity_users(tenant_id);
        CREATE INDEX ix_identity_users_provider ON identity_users(provider_id);
        CREATE UNIQUE INDEX ix_identity_users_ext ON identity_users(provider_id, external_id);

        CREATE TABLE lifecycle_actions (
            id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id        UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            action_type      VARCHAR(20)  NOT NULL,
            target_username  VARCHAR(256) NOT NULL,
            display_name     VARCHAR(256),
            email            VARCHAR(256),
            status           VARCHAR(30)  NOT NULL DEFAULT 'pending_discovery',
            requested_by     UUID         NOT NULL REFERENCES users(id),
            approved_by      UUID         REFERENCES users(id),
            notes            TEXT,
            created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
            approved_at      TIMESTAMPTZ,
            completed_at     TIMESTAMPTZ
        );
        CREATE INDEX ix_lifecycle_actions_tenant ON lifecycle_actions(tenant_id);

        CREATE TABLE lifecycle_tasks (
            id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            action_id    UUID         NOT NULL REFERENCES lifecycle_actions(id) ON DELETE CASCADE,
            system_type  VARCHAR(30)  NOT NULL,
            system_id    VARCHAR(36),
            system_name  VARCHAR(256) NOT NULL,
            status       VARCHAR(20)  NOT NULL DEFAULT 'pending',
            result       TEXT,
            error        TEXT,
            executed_at  TIMESTAMPTZ
        );
        CREATE INDEX ix_lifecycle_tasks_action ON lifecycle_tasks(action_id);
    """))


def downgrade() -> None:
    op.execute(text("""
        DROP TABLE IF EXISTS lifecycle_tasks;
        DROP TABLE IF EXISTS lifecycle_actions;
        DROP TABLE IF EXISTS identity_users;
        DROP TABLE IF EXISTS identity_providers;
    """))
