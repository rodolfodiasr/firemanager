from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.server import Server
from app.schemas.server import AnalyzeRequest, AnalyzeResponse, ServerCreate, ServerRead, ServerUpdate
from app.services.server_analysis import analyze
from app.utils.crypto import decrypt_credentials, encrypt_credentials

router = APIRouter()


def _to_read(server: Server) -> ServerRead:
    return ServerRead(
        id=server.id,
        tenant_id=server.tenant_id,
        name=server.name,
        host=server.host,
        ssh_port=server.ssh_port,
        os_type=server.os_type,
        description=server.description,
        is_active=server.is_active,
        created_at=server.created_at,
        updated_at=server.updated_at,
    )


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ServerRead])
async def list_servers(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[ServerRead]:
    result = await db.execute(
        select(Server)
        .where(Server.tenant_id == ctx.tenant.id)
        .order_by(Server.name)
    )
    return [_to_read(s) for s in result.scalars().all()]


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=ServerRead, status_code=201)
async def create_server(
    data: ServerCreate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> ServerRead:
    server = Server(
        tenant_id=ctx.tenant.id,
        name=data.name,
        host=data.host,
        ssh_port=data.ssh_port,
        os_type=data.os_type,
        description=data.description,
        encrypted_credentials=encrypt_credentials(data.credentials),
        is_active=data.is_active,
    )
    db.add(server)
    await db.flush()
    await db.refresh(server)
    return _to_read(server)


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch("/{server_id}", response_model=ServerRead)
async def update_server(
    server_id: UUID,
    data: ServerUpdate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> ServerRead:
    result = await db.execute(
        select(Server).where(Server.id == server_id, Server.tenant_id == ctx.tenant.id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Servidor não encontrado")

    if data.name is not None:        server.name = data.name
    if data.host is not None:        server.host = data.host
    if data.ssh_port is not None:    server.ssh_port = data.ssh_port
    if data.os_type is not None:     server.os_type = data.os_type
    if data.description is not None: server.description = data.description
    if data.is_active is not None:   server.is_active = data.is_active
    if data.credentials is not None:
        server.encrypted_credentials = encrypt_credentials(data.credentials)

    await db.flush()
    await db.refresh(server)
    return _to_read(server)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{server_id}", status_code=204)
async def delete_server(
    server_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(
        select(Server).where(Server.id == server_id, Server.tenant_id == ctx.tenant.id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Servidor não encontrado")
    await db.delete(server)
    await db.flush()


# ── Test SSH connection ───────────────────────────────────────────────────────

@router.post("/{server_id}/test")
async def test_server(
    server_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    from app.connectors.ssh_linux import SshLinuxConnector
    result = await db.execute(
        select(Server).where(Server.id == server_id, Server.tenant_id == ctx.tenant.id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Servidor não encontrado")

    creds = decrypt_credentials(server.encrypted_credentials)
    connector = SshLinuxConnector(
        host=server.host,
        port=server.ssh_port,
        username=creds.get("username", ""),
        password=creds.get("password", ""),
        private_key=creds.get("private_key", ""),
    )
    ok, message = await connector.ping()
    return {"success": ok, "message": message}


# ── Analyze (N3 Analyst) ──────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_servers(
    data: AnalyzeRequest,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> AnalyzeResponse:
    answer, sources = await analyze(
        db=db,
        tenant_id=ctx.tenant.id,
        question=data.question,
        server_ids=data.server_ids,
        integration_ids=data.integration_ids,
        host_filter=data.host_filter,
    )
    return AnalyzeResponse(answer=answer, sources_used=sources)
