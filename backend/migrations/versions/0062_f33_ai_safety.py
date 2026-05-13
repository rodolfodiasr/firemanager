"""F33 — IA Safety & Governança: dual-approval, maintenance windows, erasure requests.

Revision ID: 0062
Revises: 0061
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "maintenance_windows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("starts_at", sa.DateTime, nullable=False),
        sa.Column("ends_at", sa.DateTime, nullable=False),
        sa.Column("recurrence", sa.String(20), nullable=False, server_default="once"),
        sa.Column("recurrence_day", sa.Integer, nullable=True),
        sa.Column("affected_devices", JSONB, nullable=True),
        sa.Column("block_ai_operations", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("block_bulk_jobs", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_maintenance_windows_tenant_id", "maintenance_windows", ["tenant_id"])
    op.create_index("ix_maintenance_windows_tenant_active", "maintenance_windows", ["tenant_id", "is_active"])

    op.create_table(
        "approval_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("operation_context", JSONB, nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="high"),
        sa.Column("requester_id", UUID(as_uuid=True), nullable=True),
        sa.Column("requester_note", sa.Text, nullable=True),
        sa.Column("first_approver_id", UUID(as_uuid=True), nullable=True),
        sa.Column("first_approved_at", sa.DateTime, nullable=True),
        sa.Column("second_approver_id", UUID(as_uuid=True), nullable=True),
        sa.Column("second_approved_at", sa.DateTime, nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("rejected_by", UUID(as_uuid=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending_first"),
        sa.Column("requires_two_approvals", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_approval_requests_tenant_id", "approval_requests", ["tenant_id"])
    op.create_index("ix_approval_requests_tenant_status", "approval_requests", ["tenant_id", "status"])

    op.create_table(
        "erasure_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by", UUID(as_uuid=True), nullable=True),
        sa.Column("target_user_email", sa.String(255), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("legal_basis", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("affected_tables", JSONB, nullable=True),
        sa.Column("audit_summary", JSONB, nullable=True),
        sa.Column("approved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_erasure_requests_tenant_id", "erasure_requests", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("erasure_requests")
    op.drop_table("approval_requests")
    op.drop_table("maintenance_windows")
