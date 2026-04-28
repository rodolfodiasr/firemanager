from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.server import ServerOsType


class ServerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    host: str = Field(..., min_length=1, max_length=255)
    ssh_port: int = Field(22, ge=1, le=65535)
    os_type: ServerOsType = ServerOsType.linux
    description: str | None = None
    credentials: dict = Field(default_factory=dict)
    is_active: bool = True


class ServerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    host: str | None = Field(None, min_length=1, max_length=255)
    ssh_port: int | None = Field(None, ge=1, le=65535)
    os_type: ServerOsType | None = None
    description: str | None = None
    credentials: dict | None = None
    is_active: bool | None = None


class ServerRead(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    host: str
    ssh_port: int
    os_type: ServerOsType
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnalyzeRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    server_ids: list[UUID] = Field(default_factory=list)
    integration_ids: list[UUID] = Field(default_factory=list)
    host_filter: str | None = None


class AnalyzeResponse(BaseModel):
    answer: str
    sources_used: list[str]
