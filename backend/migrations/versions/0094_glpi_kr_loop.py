"""GLPI KB Knowledge Registration Loop.

Adds KB coverage classification and KR ticket/draft linking to the GLPI analysis pipeline.

Fields added:
- glpi_ticket_analyses: kb_status, kb_docs, kr_ticket_id, kr_draft_id
- glpi_integrations:    auto_create_kr, kr_category_id
- assistant_doc_drafts: glpi_analysis_id + session_id made nullable
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0094"
down_revision = "0093"


def upgrade() -> None:
    # ── glpi_ticket_analyses ──────────────────────────────────────────────────
    op.add_column("glpi_ticket_analyses", sa.Column(
        "kb_status", sa.String(40), nullable=True,
        comment="documentado | parcialmente_documentado | sem_documentacao | nao_verificado",
    ))
    op.add_column("glpi_ticket_analyses", sa.Column(
        "kb_docs", JSONB(), nullable=True,
        comment="List of KB document titles found during analysis",
    ))
    op.add_column("glpi_ticket_analyses", sa.Column(
        "kr_ticket_id", sa.Integer(), nullable=True,
        comment="GLPI ticket ID of the KR (Knowledge Registration) ticket created for this analysis",
    ))
    op.add_column("glpi_ticket_analyses", sa.Column(
        "kr_draft_id", UUID(as_uuid=True), nullable=True,
        comment="FK to assistant_doc_drafts.id — the draft generated for KR",
    ))

    # ── glpi_integrations ─────────────────────────────────────────────────────
    op.add_column("glpi_integrations", sa.Column(
        "auto_create_kr", sa.Boolean(), nullable=False, server_default="false",
        comment="Auto-open a KR ticket in GLPI when kb_status != documentado",
    ))
    op.add_column("glpi_integrations", sa.Column(
        "kr_category_id", sa.Integer(), nullable=True,
        comment="GLPI ITILCategory id to assign to auto-created KR tickets",
    ))

    # ── assistant_doc_drafts ──────────────────────────────────────────────────
    # Allow drafts originating from GLPI (no session)
    op.alter_column("assistant_doc_drafts", "session_id", nullable=True)
    op.add_column("assistant_doc_drafts", sa.Column(
        "glpi_analysis_id", UUID(as_uuid=True), nullable=True,
        comment="FK to glpi_ticket_analyses.id — set when draft was generated from GLPI KR flow",
    ))


def downgrade() -> None:
    op.drop_column("assistant_doc_drafts", "glpi_analysis_id")
    op.alter_column("assistant_doc_drafts", "session_id", nullable=False)
    op.drop_column("glpi_integrations", "kr_category_id")
    op.drop_column("glpi_integrations", "auto_create_kr")
    op.drop_column("glpi_ticket_analyses", "kr_draft_id")
    op.drop_column("glpi_ticket_analyses", "kr_ticket_id")
    op.drop_column("glpi_ticket_analyses", "kb_docs")
    op.drop_column("glpi_ticket_analyses", "kb_status")
