"""Multi-domain investigations: cross_domain_sessions + composite_investigations + sub_investigations"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0093"
down_revision = "0092"


def upgrade() -> None:
    op.create_table(
        "cross_domain_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("problem_description", sa.Text, nullable=False),
        sa.Column("domains", JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'running'")),
        sa.Column("sub_results", JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("correlation", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_cross_domain_tenant", "cross_domain_sessions", ["tenant_id"])

    op.create_table(
        "composite_investigations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_name", sa.String(200), nullable=False),
        sa.Column("symptom", sa.Text, nullable=False),
        sa.Column("domains", JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("consolidation", sa.Text, nullable=True),
        sa.Column("action_plan_session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_composite_tenant", "composite_investigations", ["tenant_id"])

    op.create_table(
        "sub_investigations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "composite_id",
            UUID(as_uuid=True),
            sa.ForeignKey("composite_investigations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("domain", sa.String(20), nullable=False),
        sa.Column("assigned_to_id", UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_to_name", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("findings", sa.Text, nullable=True),
        sa.Column("investigation_session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_sub_inv_composite", "sub_investigations", ["composite_id"])


def downgrade() -> None:
    op.drop_table("sub_investigations")
    op.drop_index("ix_composite_tenant", "composite_investigations")
    op.drop_table("composite_investigations")
    op.drop_index("ix_cross_domain_tenant", "cross_domain_sessions")
    op.drop_table("cross_domain_sessions")
