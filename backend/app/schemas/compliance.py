from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ComplianceReportRead(BaseModel):
    id: UUID
    tenant_id: UUID
    server_id: UUID
    source: str
    agent_id: str | None
    policy_id: str | None
    policy_name: str
    score_pct: float
    total_checks: int
    passed: int
    failed: int
    not_applicable: int
    controls: list
    ai_summary: str
    ai_recommendations: list
    created_at: datetime

    model_config = {"from_attributes": True}


class ComplianceReportSummary(BaseModel):
    id: UUID
    tenant_id: UUID
    server_id: UUID
    source: str
    policy_name: str
    score_pct: float
    total_checks: int
    passed: int
    failed: int
    not_applicable: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ComplianceGenerateRequest(BaseModel):
    server_id: UUID
    policy_id: str | None = None
    force_source: str | None = None  # "wazuh" | "ssh" | None (auto)


class ComplianceRemediateRequest(BaseModel):
    recommendation_index: int | None = None  # usado quando mode="recommendations"
    mode: str = "recommendations"  # "recommendations" | "controls"
