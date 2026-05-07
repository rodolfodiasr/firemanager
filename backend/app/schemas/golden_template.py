"""Pydantic schemas for Fase 17 — Golden Config Templates."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TemplateVariable(BaseModel):
    key: str
    type: str  # ip, cidr, string, integer, hostname
    label: str
    required: bool = True
    default: str | None = None
    hint: str | None = None


class GoldenTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    vendor: str = "any"
    category: str
    variables: list[TemplateVariable] = []
    content: str = ""
    change_note: str | None = None


class GoldenTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    vendor: str | None = None
    category: str | None = None
    variables: list[TemplateVariable] | None = None
    content: str | None = None
    change_note: str | None = None


class GoldenTemplateVersionRead(BaseModel):
    id: UUID
    version: int
    change_note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class GoldenTemplateRead(BaseModel):
    id: UUID
    tenant_id: UUID | None
    name: str
    description: str | None
    vendor: str
    category: str
    variables: list[dict]
    content: str
    version: int
    is_active: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GoldenTemplateSummary(BaseModel):
    id: str
    tenant_id: str | None
    name: str
    description: str | None
    vendor: str
    category: str
    variable_count: int
    version: int
    is_system: bool
    created_at: str
    updated_at: str


class RenderRequest(BaseModel):
    variable_values: dict[str, str] = {}


class RenderResponse(BaseModel):
    content: str
    unresolved: list[str]


class ApplyRequest(BaseModel):
    device_id: str
    variable_values: dict[str, str] = {}


class ApplyResponse(BaseModel):
    status: str  # "applied" | "manual" | "error"
    message: str
    output: str | None = None
    commands: str | None = None  # returned when status="manual"


class DivergenceRequest(BaseModel):
    device_id: str
    variable_values: dict[str, str] = {}


class DivergenceItem(BaseModel):
    section: str
    value: str
    status: str  # "missing" | "extra"


class DivergenceResponse(BaseModel):
    device_id: str
    template_id: str
    vendor: str
    items: list[DivergenceItem]
    summary: dict[str, int]
    rendered_preview: str
    supported: bool
    message: str | None = None


class PrefillResponse(BaseModel):
    variable_values: dict[str, str]
