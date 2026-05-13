"""F34 — Infraestrutura de Segurança Avançada: Vault, OPA, security profiles, pentest.

Revision ID: 0064
Revises: 0063
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vault_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("vault_url", sa.String(500), nullable=False),
        sa.Column("auth_method", sa.String(30), nullable=False, server_default="token"),
        sa.Column("token_encrypted", sa.Text, nullable=True),
        sa.Column("role_id", sa.String(200), nullable=True),
        sa.Column("secret_id_encrypted", sa.Text, nullable=True),
        sa.Column("default_mount", sa.String(100), nullable=False, server_default="secret"),
        sa.Column("namespace", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_verified_at", sa.DateTime, nullable=True),
        sa.Column("last_verified_ok", sa.Boolean, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_vault_configs_tenant_id", "vault_configs", ["tenant_id"])

    op.create_table(
        "vault_secret_refs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("vault_config_id", UUID(as_uuid=True), sa.ForeignKey("vault_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String(200), nullable=False),
        sa.Column("vault_path", sa.String(500), nullable=False),
        sa.Column("vault_key", sa.String(200), nullable=False, server_default="value"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "alias", name="uq_vault_secret_refs_tenant_alias"),
    )
    op.create_index("ix_vault_secret_refs_tenant_id", "vault_secret_refs", ["tenant_id"])

    op.create_table(
        "opa_policies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("package_name", sa.String(200), nullable=False, server_default="eternity"),
        sa.Column("rego_source", sa.Text, nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_opa_policies_tenant_id", "opa_policies", ["tenant_id"])

    op.create_table(
        "opa_evaluations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", UUID(as_uuid=True), sa.ForeignKey("opa_policies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("policy_name", sa.String(200), nullable=False),
        sa.Column("input_data", JSONB, nullable=True),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("allowed", sa.Boolean, nullable=True),
        sa.Column("evaluated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("evaluated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_opa_evaluations_tenant_id", "opa_evaluations", ["tenant_id"])

    op.create_table(
        "security_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("profile_type", sa.String(30), nullable=False, server_default="hardening"),
        sa.Column("controls", JSONB, nullable=True),
        sa.Column("applied_at", sa.DateTime, nullable=True),
        sa.Column("applied_by", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_security_profiles_tenant_id", "security_profiles", ["tenant_id"])

    op.create_table(
        "pentest_schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("scope", sa.Text, nullable=True),
        sa.Column("pentest_type", sa.String(30), nullable=False, server_default="external"),
        sa.Column("vendor", sa.String(200), nullable=True),
        sa.Column("scheduled_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned"),
        sa.Column("findings_critical", sa.Integer, nullable=False, server_default="0"),
        sa.Column("findings_high", sa.Integer, nullable=False, server_default="0"),
        sa.Column("findings_medium", sa.Integer, nullable=False, server_default="0"),
        sa.Column("findings_low", sa.Integer, nullable=False, server_default="0"),
        sa.Column("report_url", sa.String(500), nullable=True),
        sa.Column("remediation_deadline", sa.DateTime, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_pentest_schedules_tenant_id", "pentest_schedules", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("pentest_schedules")
    op.drop_table("security_profiles")
    op.drop_table("opa_evaluations")
    op.drop_table("opa_policies")
    op.drop_table("vault_secret_refs")
    op.drop_table("vault_configs")
