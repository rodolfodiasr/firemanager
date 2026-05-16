"""F39.cont — Self-Service Portal: access_catalog_items + access_requests.

Revision ID: 0084
Revises: 0083
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0084"
down_revision = "0083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "access_catalog_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("connector_id", UUID(as_uuid=True), nullable=True),
        sa.Column("ad_group", sa.String(200), nullable=True),
        sa.Column("access_type", sa.String(30), nullable=False, server_default="group_member"),
        sa.Column("approval_required", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("approver_role", sa.String(20), nullable=False, server_default="admin"),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_access_catalog_items_tenant", "access_catalog_items", ["tenant_id"])
    op.create_index("ix_access_catalog_items_tenant_category", "access_catalog_items", ["tenant_id", "category"])

    op.create_table(
        "access_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("catalog_item_id", UUID(as_uuid=True), sa.ForeignKey("access_catalog_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("item_name", sa.String(200), nullable=False),
        sa.Column("requester_email", sa.String(255), nullable=False),
        sa.Column("requester_name", sa.String(200), nullable=True),
        sa.Column("business_justification", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("approved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("provisioned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_access_requests_tenant", "access_requests", ["tenant_id"])
    op.create_index("ix_access_requests_tenant_status", "access_requests", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_table("access_requests")
    op.drop_table("access_catalog_items")
