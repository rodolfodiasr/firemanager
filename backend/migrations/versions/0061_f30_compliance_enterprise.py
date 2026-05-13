"""F30 — Compliance Enterprise: packs, assessments, BC/DR plans, SLA tiers.

Revision ID: 0061
Revises: 0060
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compliance_packs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("framework", sa.String(50), nullable=False),
        sa.Column("version", sa.String(20), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_builtin", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "compliance_pack_controls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("pack_id", UUID(as_uuid=True), sa.ForeignKey("compliance_packs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("control_id", sa.String(50), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("verification_type", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("evidence_hint", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_compliance_pack_controls_pack_id", "compliance_pack_controls", ["pack_id"])

    op.create_table(
        "compliance_pack_assessments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("pack_id", UUID(as_uuid=True), sa.ForeignKey("compliance_packs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pack_name", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("overall_score", sa.Float, nullable=True),
        sa.Column("compliant_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("partial_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("non_compliant_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_controls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("findings", JSONB, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_compliance_assessments_tenant_id", "compliance_pack_assessments", ["tenant_id"])

    op.create_table(
        "bcdr_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("rto_hours", sa.Integer, nullable=False, server_default="4"),
        sa.Column("rpo_hours", sa.Integer, nullable=False, server_default="1"),
        sa.Column("scope", sa.Text, nullable=True),
        sa.Column("contacts", JSONB, nullable=True),
        sa.Column("recovery_steps", JSONB, nullable=True),
        sa.Column("last_test_at", sa.DateTime, nullable=True),
        sa.Column("last_test_result", sa.String(20), nullable=True),
        sa.Column("last_test_notes", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_bcdr_plans_tenant_id", "bcdr_plans", ["tenant_id"])

    op.create_table(
        "sla_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tier_name", sa.String(50), nullable=False),
        sa.Column("response_minutes", sa.Integer, nullable=False, server_default="60"),
        sa.Column("resolution_hours", sa.Integer, nullable=False, server_default="8"),
        sa.Column("escalation_hours", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "tier_name", name="uq_sla_configs_tenant_tier"),
    )
    op.create_index("ix_sla_configs_tenant_id", "sla_configs", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("sla_configs")
    op.drop_table("bcdr_plans")
    op.drop_table("compliance_pack_assessments")
    op.drop_table("compliance_pack_controls")
    op.drop_table("compliance_packs")
