"""Fase 20: database_connectors + database_audit_reports tables

Revision ID: 0034
Revises: 0033
Create Date: 2026-05-08
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text("""
        CREATE TABLE database_connectors (
            id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            server_id    UUID         REFERENCES servers(id) ON DELETE SET NULL,
            name         VARCHAR(200) NOT NULL,
            description  TEXT,
            db_type      VARCHAR(20)  NOT NULL,
            host         VARCHAR(255) NOT NULL,
            port         INTEGER      NOT NULL,
            database_name VARCHAR(200) NOT NULL,
            encrypted_credentials TEXT NOT NULL DEFAULT '{}',
            is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
            last_tested_at   TIMESTAMPTZ,
            last_test_ok     BOOLEAN,
            last_test_error  TEXT,
            created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """))
    op.execute(text("CREATE INDEX ix_database_connectors_tenant_id ON database_connectors (tenant_id)"))

    op.execute(text("""
        CREATE TABLE database_audit_reports (
            id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            connector_id  UUID        NOT NULL REFERENCES database_connectors(id) ON DELETE CASCADE,
            status        VARCHAR(20) NOT NULL DEFAULT 'running',
            db_version    VARCHAR(200),
            user_count    INTEGER     NOT NULL DEFAULT 0,
            finding_count INTEGER     NOT NULL DEFAULT 0,
            users         JSONB       NOT NULL DEFAULT '[]',
            findings      JSONB       NOT NULL DEFAULT '[]',
            ai_summary    TEXT        NOT NULL DEFAULT '',
            ai_recommendations JSONB  NOT NULL DEFAULT '[]',
            error         TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at  TIMESTAMPTZ
        )
    """))
    op.execute(text("CREATE INDEX ix_database_audit_reports_tenant_id   ON database_audit_reports (tenant_id)"))
    op.execute(text("CREATE INDEX ix_database_audit_reports_connector_id ON database_audit_reports (connector_id)"))
    op.execute(text("CREATE INDEX ix_database_audit_reports_created_at   ON database_audit_reports (created_at DESC)"))


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS ix_database_audit_reports_created_at"))
    op.execute(text("DROP INDEX IF EXISTS ix_database_audit_reports_connector_id"))
    op.execute(text("DROP INDEX IF EXISTS ix_database_audit_reports_tenant_id"))
    op.execute(text("DROP TABLE IF EXISTS database_audit_reports"))
    op.execute(text("DROP INDEX IF EXISTS ix_database_connectors_tenant_id"))
    op.execute(text("DROP TABLE IF EXISTS database_connectors"))
