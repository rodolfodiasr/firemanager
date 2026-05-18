"""glpi kr publish destination fields

Revision ID: 0095
Revises: 0094
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0095"
down_revision = "0094"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # assistant_doc_drafts: destino de publicação escolhido pelo analista
    op.add_column("assistant_doc_drafts", sa.Column("target_book_id", sa.Integer(), nullable=True))
    op.add_column("assistant_doc_drafts", sa.Column("target_chapter_id", sa.Integer(), nullable=True))

    # glpi_integrations: destino padrão KR por integração
    op.add_column("glpi_integrations", sa.Column("kr_bookstack_book_id", sa.Integer(), nullable=True))
    op.add_column("glpi_integrations", sa.Column("kr_bookstack_chapter_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("glpi_integrations", "kr_bookstack_chapter_id")
    op.drop_column("glpi_integrations", "kr_bookstack_book_id")
    op.drop_column("assistant_doc_drafts", "target_chapter_id")
    op.drop_column("assistant_doc_drafts", "target_book_id")
