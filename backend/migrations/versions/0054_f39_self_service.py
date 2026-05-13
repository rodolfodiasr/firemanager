"""F39: Identity Self-Service — otp_requests, password_expiry_reminders.

Revision ID: 0054
Revises: 0053
Create Date: 2026-05-13
"""
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS otp_requests")
