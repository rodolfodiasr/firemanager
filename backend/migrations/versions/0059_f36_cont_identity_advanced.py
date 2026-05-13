"""F36.cont — Governança de Identidade: postura, role mining, saúde de grupos."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identity_posture_snapshots",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Integer, nullable=False),               # 0-100
        sa.Column("mfa_pct", sa.Float, nullable=True),
        sa.Column("admin_permanent_pct", sa.Float, nullable=True),    # % admins com roles permanentes
        sa.Column("campaigns_on_time_pct", sa.Float, nullable=True),
        sa.Column("sod_critical_open", sa.Integer, nullable=True),
        sa.Column("inactive_accounts", sa.Integer, nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("computed_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_identity_posture_tenant_id", "identity_posture_snapshots", ["tenant_id"])
    op.create_index("ix_identity_posture_computed_at", "identity_posture_snapshots", ["tenant_id", "computed_at"])

    op.create_table(
        "excessive_access_alerts",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), sa.ForeignKey("ad_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_type", sa.String(60), nullable=False),       # too_many_groups | multi_dept | stale_admin | excess_vs_peers
        sa.Column("details", JSONB, nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),  # open | dismissed | remediated
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_excessive_access_tenant_id", "excessive_access_alerts", ["tenant_id"])

    op.create_table(
        "group_health_reports",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_id", PG_UUID(as_uuid=True), sa.ForeignKey("ad_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("health_score", sa.Integer, nullable=False),        # 0-100
        sa.Column("issues", JSONB, nullable=True),                    # list of {type, description}
        sa.Column("analyzed_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_group_health_tenant_id", "group_health_reports", ["tenant_id"])

    op.create_table(
        "role_profiles",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_title", sa.String(200), nullable=False),
        sa.Column("department", sa.String(200), nullable=True),
        sa.Column("standard_groups", JSONB, nullable=True),           # list of group object_ids present in >80% of users
        sa.Column("computed_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_role_profiles_tenant_id", "role_profiles", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_role_profiles_tenant_id", table_name="role_profiles")
    op.drop_table("role_profiles")
    op.drop_index("ix_group_health_tenant_id", table_name="group_health_reports")
    op.drop_table("group_health_reports")
    op.drop_index("ix_excessive_access_tenant_id", table_name="excessive_access_alerts")
    op.drop_table("excessive_access_alerts")
    op.drop_index("ix_identity_posture_computed_at", table_name="identity_posture_snapshots")
    op.drop_index("ix_identity_posture_tenant_id", table_name="identity_posture_snapshots")
    op.drop_table("identity_posture_snapshots")
