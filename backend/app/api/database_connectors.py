"""API routes — Fase 20: Database Connectors & Audit."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_reviewer
from app.database import get_db
from app.utils.crypto import decrypt_credentials, encrypt_credentials

router = APIRouter()

_DB_TYPES = {"postgresql", "mysql", "mariadb", "sqlserver", "oracle"}
_DEFAULT_PORTS = {"postgresql": 5432, "mysql": 3306, "mariadb": 3306, "sqlserver": 1433, "oracle": 1521}


# ── Schemas ───────────────────────────────────────────────────────────────────

class ConnectorCreate(BaseModel):
    name: str
    description: str | None = None
    db_type: str
    host: str
    port: int | None = None
    database_name: str
    server_id: UUID | None = None
    credentials: dict  # {"username": ..., "password": ..., "ssl": False}

class ConnectorUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    server_id: UUID | None = None
    credentials: dict | None = None

class ConnectorRead(BaseModel):
    id: str
    tenant_id: str
    server_id: str | None
    name: str
    description: str | None
    db_type: str
    host: str
    port: int
    database_name: str
    is_active: bool
    last_tested_at: str | None
    last_test_ok: bool | None
    last_test_error: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, c) -> "ConnectorRead":
        return cls(
            id=str(c.id),
            tenant_id=str(c.tenant_id),
            server_id=str(c.server_id) if c.server_id else None,
            name=c.name,
            description=c.description,
            db_type=c.db_type,
            host=c.host,
            port=c.port,
            database_name=c.database_name,
            is_active=c.is_active,
            last_tested_at=c.last_tested_at.isoformat() if c.last_tested_at else None,
            last_test_ok=c.last_test_ok,
            last_test_error=c.last_test_error,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )

class TestResult(BaseModel):
    success: bool
    message: str

class AuditReportRead(BaseModel):
    id: str
    connector_id: str
    status: str
    db_version: str | None
    user_count: int
    finding_count: int
    users: list
    findings: list
    ai_summary: str
    ai_recommendations: list
    error: str | None
    created_at: str
    completed_at: str | None

    @classmethod
    def from_orm(cls, r) -> "AuditReportRead":
        return cls(
            id=str(r.id),
            connector_id=str(r.connector_id),
            status=r.status,
            db_version=r.db_version,
            user_count=r.user_count or 0,
            finding_count=r.finding_count or 0,
            users=r.users or [],
            findings=r.findings or [],
            ai_summary=r.ai_summary or "",
            ai_recommendations=r.ai_recommendations or [],
            error=r.error,
            created_at=r.created_at.isoformat(),
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
        )

class AuditSummary(BaseModel):
    id: str
    connector_id: str
    status: str
    user_count: int
    finding_count: int
    db_version: str | None
    created_at: str
    completed_at: str | None

    @classmethod
    def from_orm(cls, r) -> "AuditSummary":
        return cls(
            id=str(r.id),
            connector_id=str(r.connector_id),
            status=r.status,
            user_count=r.user_count or 0,
            finding_count=r.finding_count or 0,
            db_version=r.db_version,
            created_at=r.created_at.isoformat(),
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
        )


# ── Connectors CRUD ───────────────────────────────────────────────────────────

@router.get("", response_model=list[ConnectorRead])
async def list_connectors(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[ConnectorRead]:
    from app.models.database_connector import DatabaseConnector
    result = await db.execute(
        select(DatabaseConnector)
        .where(DatabaseConnector.tenant_id == ctx.tenant.id)
        .order_by(DatabaseConnector.name)
    )
    return [ConnectorRead.from_orm(c) for c in result.scalars().all()]


@router.post("", response_model=ConnectorRead, status_code=201)
async def create_connector(
    data: ConnectorCreate,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> ConnectorRead:
    from app.models.database_connector import DatabaseConnector
    if data.db_type not in _DB_TYPES:
        raise HTTPException(400, f"db_type inválido. Aceitos: {', '.join(sorted(_DB_TYPES))}")

    conn = DatabaseConnector(
        tenant_id=ctx.tenant.id,
        server_id=data.server_id,
        name=data.name,
        description=data.description,
        db_type=data.db_type,
        host=data.host,
        port=data.port or _DEFAULT_PORTS.get(data.db_type, 5432),
        database_name=data.database_name,
        encrypted_credentials=encrypt_credentials(data.credentials),
    )
    db.add(conn)
    await db.flush()
    await db.refresh(conn)
    await db.commit()
    await db.refresh(conn)
    return ConnectorRead.from_orm(conn)


@router.get("/{connector_id}", response_model=ConnectorRead)
async def get_connector(
    connector_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> ConnectorRead:
    from app.models.database_connector import DatabaseConnector
    conn = await db.get(DatabaseConnector, connector_id)
    if not conn or conn.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Conector não encontrado")
    return ConnectorRead.from_orm(conn)


@router.patch("/{connector_id}", response_model=ConnectorRead)
async def update_connector(
    connector_id: UUID,
    data: ConnectorUpdate,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> ConnectorRead:
    from app.models.database_connector import DatabaseConnector
    conn = await db.get(DatabaseConnector, connector_id)
    if not conn or conn.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Conector não encontrado")
    if data.name        is not None: conn.name          = data.name
    if data.description is not None: conn.description   = data.description
    if data.host        is not None: conn.host           = data.host
    if data.port        is not None: conn.port           = data.port
    if data.database_name is not None: conn.database_name = data.database_name
    if data.server_id   is not None: conn.server_id      = data.server_id
    if data.credentials is not None: conn.encrypted_credentials = encrypt_credentials(data.credentials)
    await db.commit()
    await db.refresh(conn)
    return ConnectorRead.from_orm(conn)


@router.delete("/{connector_id}")
async def delete_connector(
    connector_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    from app.models.database_connector import DatabaseConnector
    conn = await db.get(DatabaseConnector, connector_id)
    if not conn or conn.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Conector não encontrado")
    await db.delete(conn)
    await db.commit()
    return Response(status_code=204)


# ── Test connection ───────────────────────────────────────────────────────────

@router.post("/{connector_id}/test", response_model=TestResult)
async def test_connector(
    connector_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> TestResult:
    from app.models.database_connector import DatabaseConnector
    from app.services.db_audit_service import test_connection

    conn = await db.get(DatabaseConnector, connector_id)
    if not conn or conn.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Conector não encontrado")

    ok, msg = await test_connection(conn)
    conn.last_tested_at  = datetime.now(timezone.utc)
    conn.last_test_ok    = ok
    conn.last_test_error = None if ok else msg[:500]
    await db.commit()

    return TestResult(success=ok, message=msg)


# ── Audit ─────────────────────────────────────────────────────────────────────

@router.post("/{connector_id}/audit", response_model=AuditReportRead)
async def run_audit(
    connector_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> AuditReportRead:
    from app.models.database_connector import DatabaseConnector
    from app.services.db_audit_service import run_audit as _run

    conn = await db.get(DatabaseConnector, connector_id)
    if not conn or conn.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Conector não encontrado")

    report = await _run(db, connector_id, ctx.tenant.id)
    return AuditReportRead.from_orm(report)


@router.get("/{connector_id}/audits", response_model=list[AuditSummary])
async def list_audits(
    connector_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[AuditSummary]:
    from app.models.database_connector import DatabaseAuditReport, DatabaseConnector
    conn = await db.get(DatabaseConnector, connector_id)
    if not conn or conn.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Conector não encontrado")

    result = await db.execute(
        select(DatabaseAuditReport)
        .where(DatabaseAuditReport.connector_id == connector_id)
        .order_by(DatabaseAuditReport.created_at.desc())
        .limit(20)
    )
    return [AuditSummary.from_orm(r) for r in result.scalars().all()]


@router.get("/{connector_id}/audits/{audit_id}", response_model=AuditReportRead)
async def get_audit(
    connector_id: UUID,
    audit_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> AuditReportRead:
    from app.models.database_connector import DatabaseAuditReport, DatabaseConnector
    conn = await db.get(DatabaseConnector, connector_id)
    if not conn or conn.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Conector não encontrado")
    report = await db.get(DatabaseAuditReport, audit_id)
    if not report or report.connector_id != connector_id:
        raise HTTPException(404, "Auditoria não encontrada")
    return AuditReportRead.from_orm(report)
