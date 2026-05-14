"""investigation: investigation sessions, phases and messages for iterative diagnostics.

Revision ID: 0076
Revises: 0075
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investigation_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        # Target — at most one of device_id or server_id is set
        sa.Column("device_id", UUID(as_uuid=True), nullable=True),
        sa.Column("server_id", UUID(as_uuid=True), nullable=True),
        sa.Column("integration_ids", JSONB, nullable=True),  # list of UUID strings for N3
        sa.Column("agent_type", sa.String(20), nullable=False),  # network|firewall|n3|unified
        sa.Column("problem_description", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="planning"),
        sa.Column("current_phase", sa.Integer, nullable=False, server_default="0"),
        sa.Column("synthesis", sa.Text, nullable=True),
        sa.Column("cross_domain_detected", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("cross_domain_hint", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"), onupdate=sa.text("now()")),
    )
    op.create_index("ix_investigation_sessions_tenant", "investigation_sessions", ["tenant_id"])

    op.create_table(
        "investigation_phases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("investigation_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phase_number", sa.Integer, nullable=False),
        sa.Column("phase_name", sa.String(200), nullable=False),
        sa.Column("phase_purpose", sa.Text, nullable=True),
        sa.Column("commands", JSONB, nullable=False, server_default="[]"),  # list of str
        sa.Column("raw_output", sa.Text, nullable=True),
        sa.Column("analysis", sa.Text, nullable=True),
        sa.Column("findings", JSONB, nullable=True, server_default="[]"),  # list of str
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_investigation_phases_session", "investigation_phases", ["session_id"])

    op.create_table(
        "investigation_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("investigation_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),  # user|assistant
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("phase_number", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_investigation_messages_session", "investigation_messages", ["session_id"])


def downgrade() -> None:
    op.drop_table("investigation_messages")
    op.drop_table("investigation_phases")
    op.drop_table("investigation_sessions")
