"""0088 — RMM: tabela rmm_script_templates para templates de scripts/comandos."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision = "0088"
down_revision = "0087"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rmm_script_templates",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("shell", sa.String(20), nullable=False, server_default="powershell"),
        sa.Column("run_type", sa.String(10), nullable=False, server_default="command"),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("is_builtin", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_rmm_script_templates_tenant", "rmm_script_templates", ["tenant_id"])
    op.create_index("ix_rmm_script_templates_builtin", "rmm_script_templates", ["is_builtin"])


def downgrade() -> None:
    op.drop_index("ix_rmm_script_templates_builtin")
    op.drop_index("ix_rmm_script_templates_tenant")
    op.drop_table("rmm_script_templates")
