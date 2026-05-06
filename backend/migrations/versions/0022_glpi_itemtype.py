"""Add glpi_itemtype to glpi_ticket_analyses

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "glpi_ticket_analyses",
        sa.Column(
            "glpi_itemtype",
            sa.String(50),
            nullable=False,
            server_default="Problem",
        ),
    )
    op.create_index(
        "ix_glpi_ticket_analyses_itemtype",
        "glpi_ticket_analyses",
        ["glpi_itemtype"],
    )


def downgrade() -> None:
    op.drop_index("ix_glpi_ticket_analyses_itemtype", table_name="glpi_ticket_analyses")
    op.drop_column("glpi_ticket_analyses", "glpi_itemtype")
