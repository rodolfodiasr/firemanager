"""Add similar_docs column to assistant_doc_drafts."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assistant_doc_drafts",
        sa.Column("similar_docs", JSONB, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("assistant_doc_drafts", "similar_docs")
