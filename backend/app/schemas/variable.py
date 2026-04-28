from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.variable import VariableType


# ── Tenant Variables ──────────────────────────────────────────────────────────

class TenantVariableCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    value: str
    variable_type: VariableType = VariableType.string
    description: str | None = None


class TenantVariableUpdate(BaseModel):
    value: str | None = None
    variable_type: VariableType | None = None
    description: str | None = None


class TenantVariableRead(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    value: str
    variable_type: VariableType
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Device Variables ──────────────────────────────────────────────────────────

class DeviceVariableCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    value: str
    variable_type: VariableType = VariableType.string
    description: str | None = None


class DeviceVariableUpdate(BaseModel):
    value: str | None = None
    variable_type: VariableType | None = None
    description: str | None = None


class DeviceVariableRead(BaseModel):
    id: UUID
    device_id: UUID
    tenant_id: UUID
    name: str
    value: str
    variable_type: VariableType
    description: str | None
    # Indica se este valor sobrescreve uma variável do tenant de mesmo nome
    overrides_tenant: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Resolved variable (used in preview) ──────────────────────────────────────

class ResolvedVariable(BaseModel):
    name: str
    value: str
    variable_type: VariableType
    source: str  # "device" | "tenant"


# ── Preview ───────────────────────────────────────────────────────────────────

class DevicePreview(BaseModel):
    device_id: UUID
    device_name: str
    original_input: str
    resolved_input: str
    variables_resolved: list[ResolvedVariable]
    unresolved_variables: list[str]  # variáveis {{name}} sem valor cadastrado
    ready: bool  # True se nenhuma variável ficou sem resolver


class BulkJobPreviewRequest(BaseModel):
    device_ids: list[UUID]
    natural_language_input: str


class BulkJobPreviewResponse(BaseModel):
    original_input: str
    devices: list[DevicePreview]
    all_ready: bool  # True se todos os devices resolveram 100% das variáveis
