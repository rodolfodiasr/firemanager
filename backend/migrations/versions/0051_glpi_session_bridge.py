"""Add GLPI bridge fields to assistant_sessions."""
from alembic import op
import sqlalchemy as sa

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assistant_sessions",
        sa.Column("glpi_ticket_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "assistant_sessions",
        sa.Column(
            "glpi_integration_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "assistant_sessions",
        sa.Column("glpi_itemtype", sa.String(50), nullable=True),
    )
    op.add_column(
        "assistant_sessions",
        sa.Column("glpi_ticket_title", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_assistant_sessions_glpi_ticket_id",
        "assistant_sessions",
        ["glpi_ticket_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_sessions_glpi_ticket_id", table_name="assistant_sessions")
    op.drop_column("assistant_sessions", "glpi_ticket_title")
    op.drop_column("assistant_sessions", "glpi_itemtype")
    op.drop_column("assistant_sessions", "glpi_integration_id")
    op.drop_column("assistant_sessions", "glpi_ticket_id")
