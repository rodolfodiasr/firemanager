"""0089 — Investigation: campos RMM (rmm_integration_id, rmm_agent_external_id)."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision = "0089"
down_revision = "0088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "investigation_sessions",
        sa.Column("rmm_integration_id", PG_UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "investigation_sessions",
        sa.Column("rmm_agent_external_id", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("investigation_sessions", "rmm_agent_external_id")
    op.drop_column("investigation_sessions", "rmm_integration_id")
