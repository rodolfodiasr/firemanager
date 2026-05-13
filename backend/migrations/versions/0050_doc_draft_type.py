"""Add doc_type column to assistant_doc_drafts."""
from alembic import op
import sqlalchemy as sa

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assistant_doc_drafts",
        sa.Column("doc_type", sa.String(20), nullable=False, server_default="knowledge"),
    )


def downgrade() -> None:
    op.drop_column("assistant_doc_drafts", "doc_type")
