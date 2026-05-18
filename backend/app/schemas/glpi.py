from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, HttpUrl, field_validator

from app.models.glpi_ticket_analysis import GlpiAnalysisStatus


class GlpiIntegrationCreate(BaseModel):
    glpi_url: str
    app_token: str
    username: str
    password: str                   # plaintext — encrypted server-side
    verify_ssl: bool = True
    min_priority: int = 3
    trigger_types: list[int] = [1, 2]
    trigger_categories: list[int] = []
    tag_analyzed: str = "fm-analyzed"
    poll_interval_minutes: int = 5
    lookback_hours: int = 24
    # Analysis mode & enrichment sources
    auto_analysis_enabled: bool = True
    enrich_zabbix: bool = False
    enrich_wazuh: bool = False
    enrich_device_logs: bool = False
    device_logs_timeout_seconds: int = 30
    auto_correlate_devices: bool = True
    unmatched_to_manual_queue: bool = True
    force_analysis_on_security: bool = True
    force_analysis_on_recurrent: bool = False
    # KR loop
    auto_create_kr: bool = False
    kr_category_id: int | None = None
    kr_bookstack_book_id: int | None = None
    kr_bookstack_chapter_id: int | None = None

    @field_validator("glpi_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("min_priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        if not 1 <= v <= 6:
            raise ValueError("min_priority deve estar entre 1 e 6")
        return v

    @field_validator("device_logs_timeout_seconds")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if not 5 <= v <= 300:
            raise ValueError("device_logs_timeout_seconds deve estar entre 5 e 300")
        return v


class GlpiIntegrationUpdate(BaseModel):
    glpi_url: str | None = None
    app_token: str | None = None
    username: str | None = None
    password: str | None = None     # if None, keep existing password
    verify_ssl: bool | None = None
    is_active: bool | None = None
    min_priority: int | None = None
    trigger_types: list[int] | None = None
    trigger_categories: list[int] | None = None
    tag_analyzed: str | None = None
    poll_interval_minutes: int | None = None
    lookback_hours: int | None = None
    # Analysis mode & enrichment sources
    auto_analysis_enabled: bool | None = None
    enrich_zabbix: bool | None = None
    enrich_wazuh: bool | None = None
    enrich_device_logs: bool | None = None
    device_logs_timeout_seconds: int | None = None
    auto_correlate_devices: bool | None = None
    unmatched_to_manual_queue: bool | None = None
    force_analysis_on_security: bool | None = None
    force_analysis_on_recurrent: bool | None = None
    # KR loop
    auto_create_kr: bool | None = None
    kr_category_id: int | None = None
    kr_bookstack_book_id: int | None = None
    kr_bookstack_chapter_id: int | None = None

    @field_validator("glpi_url")
    @classmethod
    def strip_trailing_slash(cls, v: str | None) -> str | None:
        return v.rstrip("/") if v else v


class GlpiIntegrationRead(BaseModel):
    id: UUID
    tenant_id: UUID
    glpi_url: str
    app_token: str
    username: str
    verify_ssl: bool
    is_active: bool
    min_priority: int
    trigger_types: list
    trigger_categories: list
    tag_analyzed: str
    poll_interval_minutes: int
    lookback_hours: int
    # Analysis mode & enrichment sources
    auto_analysis_enabled: bool
    enrich_zabbix: bool
    enrich_wazuh: bool
    enrich_device_logs: bool
    device_logs_timeout_seconds: int
    auto_correlate_devices: bool
    unmatched_to_manual_queue: bool
    force_analysis_on_security: bool
    force_analysis_on_recurrent: bool
    # KR loop
    auto_create_kr: bool
    kr_category_id: int | None
    kr_bookstack_book_id: int | None
    kr_bookstack_chapter_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GlpiTestResult(BaseModel):
    success: bool
    message: str
    glpi_version: str | None = None
    latency_ms: float | None = None


class GlpiRunAnalysisRequest(BaseModel):
    device_ids: list[str] = []


class GlpiAnalysisListItem(BaseModel):
    id: UUID
    glpi_ticket_id: int
    glpi_itemtype: str
    glpi_ticket_title: str
    status: GlpiAnalysisStatus
    confianca: float | None
    is_security_incident: bool | None
    is_recurrent: bool | None
    recurrence_count: int | None
    kb_status: str | None = None
    kr_ticket_id: int | None = None
    kr_draft_id: UUID | None = None
    created_at: datetime
    glpi_url: str | None = None

    model_config = {"from_attributes": True}


class GlpiTicketAnalysisRead(BaseModel):
    id: UUID
    tenant_id: UUID
    glpi_integration_id: UUID
    glpi_ticket_id: int
    glpi_itemtype: str
    glpi_ticket_title: str
    glpi_ticket_content: str | None
    status: GlpiAnalysisStatus
    diagnostico: str | None
    acoes_imediatas: str | None
    plano_remediacao: str | None
    causa_raiz: str | None
    prevencao: str | None
    confianca: float | None
    is_security_incident: bool | None
    is_recurrent: bool | None
    recurrence_count: int | None
    related_ticket_ids: list | None
    glpi_followup_id: int | None
    error_message: str | None
    kb_status: str | None = None
    kb_docs: list | None = None
    kr_ticket_id: int | None = None
    kr_draft_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    glpi_url: str | None = None

    model_config = {"from_attributes": True}
