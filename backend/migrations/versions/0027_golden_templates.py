"""golden_templates: Fase 17 — Golden Config template library and versioning

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "golden_templates",
        sa.Column("id",            UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id",     UUID(as_uuid=True), sa.ForeignKey("tenants.id",  ondelete="CASCADE"), nullable=True,  index=True),
        sa.Column("name",          sa.String(200),  nullable=False),
        sa.Column("description",   sa.Text,         nullable=True),
        sa.Column("vendor",        sa.String(50),   nullable=False, server_default="any"),
        sa.Column("category",      sa.String(50),   nullable=False),
        sa.Column("variables",     JSONB,            nullable=False, server_default="[]"),
        sa.Column("content",       sa.Text,         nullable=False, server_default=""),
        sa.Column("version",       sa.Integer,      nullable=False, server_default="1"),
        sa.Column("is_active",     sa.Boolean,      nullable=False, server_default="true"),
        sa.Column("is_system",     sa.Boolean,      nullable=False, server_default="false"),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id",    ondelete="SET NULL"), nullable=True),
        sa.Column("created_at",    sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at",    sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "golden_template_versions",
        sa.Column("id",            UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id",   UUID(as_uuid=True), sa.ForeignKey("golden_templates.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version",       sa.Integer,      nullable=False),
        sa.Column("content",       sa.Text,         nullable=False),
        sa.Column("variables",     JSONB,            nullable=False, server_default="[]"),
        sa.Column("change_note",   sa.String(500),  nullable=True),
        sa.Column("changed_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id",    ondelete="SET NULL"), nullable=True),
        sa.Column("created_at",    sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("golden_template_versions")
    op.drop_table("golden_templates")
