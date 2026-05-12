"""Fase 40 — Firmware Intelligence: histórico de firmware, CVEs do NVD, correlação automática.

Revision ID: 0043
Revises: 0042
Create Date: 2026-05-12
"""
from alembic import op
from sqlalchemy import text

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Histórico de versões de firmware lidas de cada device
    op.execute(text("""
        CREATE TABLE IF NOT EXISTS device_firmware_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
            version VARCHAR(100) NOT NULL,
            vendor_label VARCHAR(100) NOT NULL,
            model VARCHAR(200),
            build VARCHAR(50),
            read_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            read_method VARCHAR(20) NOT NULL DEFAULT 'rest',
            raw_output TEXT
        )
    """))

    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_device_fw_versions_device
        ON device_firmware_versions(device_id)
    """))

    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_device_fw_versions_read_at
        ON device_firmware_versions(device_id, read_at DESC)
    """))

    # CVEs do NVD indexadas por vendor/produto
    op.execute(text("""
        CREATE TABLE IF NOT EXISTS firmware_cves (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            cve_id VARCHAR(30) NOT NULL UNIQUE,
            vendor VARCHAR(50) NOT NULL,
            product VARCHAR(100) NOT NULL,
            affected_versions JSONB NOT NULL DEFAULT '{}',
            cvss_v3 FLOAT,
            cvss_v2 FLOAT,
            severity VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
            description TEXT NOT NULL DEFAULT '',
            published_at TIMESTAMPTZ,
            modified_at TIMESTAMPTZ,
            cpe_uri VARCHAR(500),
            nvd_url VARCHAR(300) NOT NULL DEFAULT '',
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_firmware_cves_vendor_product
        ON firmware_cves(vendor, product)
    """))

    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_firmware_cves_severity
        ON firmware_cves(severity)
    """))

    # Vínculo device × CVE detectada
    op.execute(text("""
        CREATE TABLE IF NOT EXISTS device_firmware_vulnerabilities (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
            cve_id VARCHAR(30) NOT NULL,
            device_version VARCHAR(100) NOT NULL,
            detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            accepted_by UUID,
            accepted_reason TEXT,
            patched_at TIMESTAMPTZ,
            UNIQUE(device_id, cve_id)
        )
    """))

    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_device_fw_vulns_device_status
        ON device_firmware_vulnerabilities(device_id, status)
    """))

    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_device_fw_vulns_cve
        ON device_firmware_vulnerabilities(cve_id)
    """))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS device_firmware_vulnerabilities CASCADE"))
    op.execute(text("DROP TABLE IF EXISTS firmware_cves CASCADE"))
    op.execute(text("DROP TABLE IF EXISTS device_firmware_versions CASCADE"))
