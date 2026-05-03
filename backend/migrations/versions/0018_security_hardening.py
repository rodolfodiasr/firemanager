"""Platform security hardening — audit log immutability, RLS, multi-sig fields

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-03

Changes:
  P2 — Row-Level Security: enable RLS on audit_logs with permissive base policy
       (restrictive per-tenant policies to be added in a future migration once
        app.current_tenant_id session variable is wired into get_db).
  P3 — Audit log immutability: trigger prevents UPDATE/DELETE on audit_logs
       regardless of who executes it (defense-in-depth).
  P6 — Multi-sig approval: add risk_level, required_approvals, co_approvals
       columns to operations table.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── P6: Multi-sig columns on operations ──────────────────────────────────
    op.add_column(
        "operations",
        sa.Column(
            "risk_level",
            sa.String(20),
            nullable=False,
            server_default="medium",
        ),
    )
    op.add_column(
        "operations",
        sa.Column(
            "required_approvals",
            sa.Integer,
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "operations",
        sa.Column(
            "co_approvals",
            JSONB,
            nullable=False,
            server_default="'[]'::jsonb",
        ),
    )
    op.create_index(
        "ix_operations_risk_level",
        "operations",
        ["risk_level"],
    )

    # ── P3: Immutable audit log — trigger blocks UPDATE and DELETE ────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        BEGIN
            RAISE EXCEPTION
                'audit_logs is append-only: UPDATE and DELETE are not permitted. '
                'Operation: %, Table: audit_logs', TG_OP;
        END;
        $$;
    """)

    op.execute("""
        CREATE TRIGGER audit_logs_immutable_update
            BEFORE UPDATE ON audit_logs
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_log_modification();
    """)

    op.execute("""
        CREATE TRIGGER audit_logs_immutable_delete
            BEFORE DELETE ON audit_logs
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_log_modification();
    """)

    # ── P2: Row-Level Security on audit_logs ─────────────────────────────────
    # Enable RLS so the framework is in place. The permissive policy below
    # preserves existing behaviour (no access restriction yet). Restrictive
    # per-tenant policies will replace this once get_db sets the session
    # variable app.current_tenant_id on every request.
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY audit_logs_base_allow
            ON audit_logs
            FOR ALL
            USING (true)
            WITH CHECK (true);
    """)

    # ── P2: RLS on devices — base permissive policy (same rationale) ─────────
    op.execute("ALTER TABLE devices ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE devices FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY devices_base_allow
            ON devices
            FOR ALL
            USING (true)
            WITH CHECK (true);
    """)

    # ── P2: RLS on operations — base permissive policy ────────────────────────
    op.execute("ALTER TABLE operations ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE operations FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY operations_base_allow
            ON operations
            FOR ALL
            USING (true)
            WITH CHECK (true);
    """)


def downgrade() -> None:
    # Remove RLS from operations
    op.execute("DROP POLICY IF EXISTS operations_base_allow ON operations;")
    op.execute("ALTER TABLE operations DISABLE ROW LEVEL SECURITY;")

    # Remove RLS from devices
    op.execute("DROP POLICY IF EXISTS devices_base_allow ON devices;")
    op.execute("ALTER TABLE devices DISABLE ROW LEVEL SECURITY;")

    # Remove RLS from audit_logs
    op.execute("DROP POLICY IF EXISTS audit_logs_base_allow ON audit_logs;")
    op.execute("ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY;")

    # Remove immutability triggers
    op.execute("DROP TRIGGER IF EXISTS audit_logs_immutable_delete ON audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_immutable_update ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification();")

    # Remove P6 columns
    op.drop_index("ix_operations_risk_level", table_name="operations")
    op.drop_column("operations", "co_approvals")
    op.drop_column("operations", "required_approvals")
    op.drop_column("operations", "risk_level")
