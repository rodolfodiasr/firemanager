"""Add analysis mode and enrichment source controls to glpi_integrations

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-06

Adds per-tenant controls for:
- auto_analysis_enabled: toggle automatic Claude analysis on/off
- enrich_zabbix / enrich_wazuh / enrich_device_logs: granular source selection
- device_logs_timeout_seconds: SSH timeout for device log collection
- auto_correlate_devices: extract IP/hostname from ticket text to find devices
- unmatched_to_manual_queue: tickets without correlation go to pending_manual
- force_analysis_on_security: bypass priority filter for security incidents
- force_analysis_on_recurrent: bypass priority filter for recurrent tickets

Also adds 'pending_manual' value to glpi_ticket_analyses.status enum.
"""
from alembic import op
import sqlalchemy as sa


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Analysis mode controls on glpi_integrations ───────────────────────────
    op.add_column("glpi_integrations", sa.Column(
        "auto_analysis_enabled", sa.Boolean(), nullable=False, server_default="true"
    ))
    op.add_column("glpi_integrations", sa.Column(
        "enrich_zabbix", sa.Boolean(), nullable=False, server_default="false"
    ))
    op.add_column("glpi_integrations", sa.Column(
        "enrich_wazuh", sa.Boolean(), nullable=False, server_default="false"
    ))
    op.add_column("glpi_integrations", sa.Column(
        "enrich_device_logs", sa.Boolean(), nullable=False, server_default="false"
    ))
    op.add_column("glpi_integrations", sa.Column(
        "device_logs_timeout_seconds", sa.Integer(), nullable=False, server_default="30"
    ))
    op.add_column("glpi_integrations", sa.Column(
        "auto_correlate_devices", sa.Boolean(), nullable=False, server_default="true"
    ))
    op.add_column("glpi_integrations", sa.Column(
        "unmatched_to_manual_queue", sa.Boolean(), nullable=False, server_default="true"
    ))
    op.add_column("glpi_integrations", sa.Column(
        "force_analysis_on_security", sa.Boolean(), nullable=False, server_default="true"
    ))
    op.add_column("glpi_integrations", sa.Column(
        "force_analysis_on_recurrent", sa.Boolean(), nullable=False, server_default="false"
    ))

    # ── Add 'pending_manual' to the status enum on glpi_ticket_analyses ───────
    # The status column uses native_enum=False (VARCHAR), so we just need to
    # ensure existing check constraints (if any) allow the new value.
    # No ALTER TYPE needed — the column is a plain VARCHAR with app-level enum.


def downgrade() -> None:
    for col in [
        "auto_analysis_enabled",
        "enrich_zabbix",
        "enrich_wazuh",
        "enrich_device_logs",
        "device_logs_timeout_seconds",
        "auto_correlate_devices",
        "unmatched_to_manual_queue",
        "force_analysis_on_security",
        "force_analysis_on_recurrent",
    ]:
        op.drop_column("glpi_integrations", col)
