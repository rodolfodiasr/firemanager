"""connectivity_analyses: Fase 18 — Network Connectivity Analysis

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE connectivity_status AS ENUM ('pending', 'running', 'completed', 'failed')")

    op.create_table(
        "connectivity_analyses",
        sa.Column("id",            UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id",     UUID(as_uuid=True), sa.ForeignKey("tenants.id",  ondelete="CASCADE"), nullable=True,  index=True),
        sa.Column("device_id",     UUID(as_uuid=True), sa.ForeignKey("devices.id",  ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status",        sa.Enum("pending", "running", "completed", "failed", name="connectivity_status"), nullable=False, server_default="pending"),
        sa.Column("routes",        JSONB, nullable=True),
        sa.Column("bgp_peers",     JSONB, nullable=True),
        sa.Column("ospf_neighbors",JSONB, nullable=True),
        sa.Column("sdwan_services",JSONB, nullable=True),
        sa.Column("anomalies",     JSONB, nullable=True),
        sa.Column("ai_summary",    sa.Text, nullable=True),
        sa.Column("ai_recommendations", JSONB, nullable=True),
        sa.Column("error",         sa.Text, nullable=True),
        sa.Column("created_at",    sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at",  sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("connectivity_analyses")
    op.execute("DROP TYPE IF EXISTS connectivity_status")
