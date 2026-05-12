from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FirmwareVersionRead(BaseModel):
    id: UUID
    device_id: UUID
    version: str
    vendor_label: str
    model: str | None
    build: str | None
    read_at: datetime
    read_method: str

    model_config = {"from_attributes": True}


class FirmwareCVERead(BaseModel):
    id: UUID
    cve_id: str
    vendor: str
    product: str
    affected_versions: dict
    cvss_v3: float | None
    cvss_v2: float | None
    severity: str
    description: str
    published_at: datetime | None
    nvd_url: str
    synced_at: datetime

    model_config = {"from_attributes": True}


class FirmwareVulnRead(BaseModel):
    id: UUID
    device_id: UUID
    cve_id: str
    device_version: str
    detected_at: datetime
    status: str
    accepted_by: UUID | None
    accepted_reason: str | None
    patched_at: datetime | None
    cve: FirmwareCVERead | None = None

    model_config = {"from_attributes": True}


class FirmwareVulnAccept(BaseModel):
    reason: str


class DeviceFirmwareSummary(BaseModel):
    device_id: UUID
    current_version: str | None
    last_read_at: datetime | None
    open_cves: int
    critical_cves: int
    high_cves: int
    worst_severity: str


class FirmwareRiskSummary(BaseModel):
    devices_with_vulns: int
    total_open_cves: int
    critical_cves: int
    high_cves: int
    top_affected: list[DeviceFirmwareSummary]
