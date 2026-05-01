"""pgvector extension + bookstack_embeddings table

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-01

Changes:
  - Enable pgvector extension
  - Create bookstack_embeddings table (1536-dim vectors, IVFFlat index)
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    op.execute(text("""
        CREATE TABLE bookstack_embeddings (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID        NOT NULL REFERENCES tenants(id)     ON DELETE CASCADE,
            integration_id UUID     NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
            bs_page_id  INTEGER     NOT NULL,
            bs_page_name VARCHAR(500) NOT NULL,
            bs_page_url VARCHAR(1000) NOT NULL,
            chunk_index INTEGER     NOT NULL,
            chunk_text  TEXT        NOT NULL,
            content_hash VARCHAR(64) NOT NULL,
            embedding   vector(1536) NOT NULL,
            indexed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_bs_chunk UNIQUE (integration_id, bs_page_id, chunk_index)
        )
    """))

    op.execute(text(
        "CREATE INDEX ix_bookstack_embeddings_tenant_id "
        "ON bookstack_embeddings (tenant_id)"
    ))
    op.execute(text(
        "CREATE INDEX ix_bookstack_embeddings_integration_id "
        "ON bookstack_embeddings (integration_id)"
    ))
    # IVFFlat approximate nearest-neighbour index (cosine distance)
    # lists=50 is a reasonable default; tune up when row count exceeds ~10k
    op.execute(text(
        "CREATE INDEX ix_bookstack_embeddings_vector "
        "ON bookstack_embeddings "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)"
    ))


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS ix_bookstack_embeddings_vector"))
    op.execute(text("DROP INDEX IF EXISTS ix_bookstack_embeddings_integration_id"))
    op.execute(text("DROP INDEX IF EXISTS ix_bookstack_embeddings_tenant_id"))
    op.execute(text("DROP TABLE IF EXISTS bookstack_embeddings"))
