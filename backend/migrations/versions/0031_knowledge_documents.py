"""Fase 19: knowledge_documents + knowledge_chunks tables

Revision ID: 0031
Revises: 0030
Create Date: 2026-05-07
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text("""
        CREATE TABLE knowledge_documents (
            id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name        VARCHAR(500) NOT NULL,
            description TEXT,
            file_type   VARCHAR(20)  NOT NULL,
            file_size   INTEGER,
            content     TEXT,
            status      VARCHAR(20)  NOT NULL DEFAULT 'pending',
            chunk_count INTEGER      NOT NULL DEFAULT 0,
            error       TEXT,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """))
    op.execute(text(
        "CREATE INDEX ix_knowledge_documents_tenant_id ON knowledge_documents (tenant_id)"
    ))

    op.execute(text("""
        CREATE TABLE knowledge_chunks (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    UUID        NOT NULL REFERENCES tenants(id)              ON DELETE CASCADE,
            document_id  UUID        NOT NULL REFERENCES knowledge_documents(id)  ON DELETE CASCADE,
            chunk_index  INTEGER     NOT NULL,
            chunk_text   TEXT        NOT NULL,
            content_hash VARCHAR(64) NOT NULL,
            embedding    vector(1536) NOT NULL,
            indexed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_knowledge_chunk UNIQUE (document_id, chunk_index)
        )
    """))
    op.execute(text(
        "CREATE INDEX ix_knowledge_chunks_tenant_id ON knowledge_chunks (tenant_id)"
    ))
    op.execute(text(
        "CREATE INDEX ix_knowledge_chunks_document_id ON knowledge_chunks (document_id)"
    ))
    op.execute(text(
        "CREATE INDEX ix_knowledge_chunks_vector "
        "ON knowledge_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)"
    ))


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS ix_knowledge_chunks_vector"))
    op.execute(text("DROP INDEX IF EXISTS ix_knowledge_chunks_document_id"))
    op.execute(text("DROP INDEX IF EXISTS ix_knowledge_chunks_tenant_id"))
    op.execute(text("DROP TABLE IF EXISTS knowledge_chunks"))
    op.execute(text("DROP INDEX IF EXISTS ix_knowledge_documents_tenant_id"))
    op.execute(text("DROP TABLE IF EXISTS knowledge_documents"))
