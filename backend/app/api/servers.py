from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.analysis_session import AnalysisSession
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


# ── Servers CRUD ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[ServerRead])
async def list_servers(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[ServerRead]:
    result = await db.execute(
        select(Server).where(Server.tenant_id == ctx.tenant.id).order_by(Server.name)
    )
    return [_to_read(s) for s in result.scalars().all()]


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


@router.post("/{server_id}/test")
async def test_server(
    server_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    from app.connectors.ssh_linux import SshLinuxConnector
    from app.connectors.winrm_windows import WinRMConnector
    from app.models.server import ServerOsType

    result = await db.execute(
        select(Server).where(Server.id == server_id, Server.tenant_id == ctx.tenant.id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Servidor não encontrado")

    creds = decrypt_credentials(server.encrypted_credentials)

    if server.os_type == ServerOsType.windows:
        connector: SshLinuxConnector | WinRMConnector = WinRMConnector(
            host=server.host,
            port=server.ssh_port,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            auth_type=creds.get("auth_type", "ntlm"),
            verify_ssl=creds.get("verify_ssl", False),
        )
    else:
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

    session = AnalysisSession(
        tenant_id=ctx.tenant.id,
        question=data.question,
        answer=answer,
        sources_used=sources,
        server_ids=[str(sid) for sid in data.server_ids],
        integration_ids=[str(iid) for iid in data.integration_ids],
        host_filter=data.host_filter,
    )
    db.add(session)
    await db.flush()

    return AnalyzeResponse(answer=answer, sources_used=sources)


# ── Session history ───────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(
    ctx:   Annotated[TenantContext, Depends(get_tenant_context)],
    db:    Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[dict]:
    result = await db.execute(
        select(AnalysisSession)
        .where(AnalysisSession.tenant_id == ctx.tenant.id)
        .order_by(desc(AnalysisSession.created_at))
        .limit(limit)
    )
    sessions = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "question": s.question,
            "answer": s.answer,
            "sources_used": s.sources_used,
            "server_ids": s.server_ids,
            "integration_ids": s.integration_ids,
            "host_filter": s.host_filter,
            "created_at": s.created_at.isoformat(),
        }
        for s in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(
        select(AnalysisSession).where(
            AnalysisSession.id == session_id,
            AnalysisSession.tenant_id == ctx.tenant.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    await db.delete(session)
    await db.flush()


# ── PDF export ────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/export-pdf")
async def export_session_pdf(
    session_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    result = await db.execute(
        select(AnalysisSession).where(
            AnalysisSession.id == session_id,
            AnalysisSession.tenant_id == ctx.tenant.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    try:
        from weasyprint import HTML
        import io

        html = _build_session_pdf_html(session)
        pdf_bytes = HTML(string=html).write_pdf()

        filename = f"analise_{session.created_at.strftime('%Y%m%d_%H%M')}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {exc}")


def _build_session_pdf_html(session: AnalysisSession) -> str:
    sources_html = "".join(
        f'<span class="source">{s}</span>' for s in (session.sources_used or [])
    )
    answer_html = session.answer.replace("\n", "<br>")
    created = session.created_at.strftime("%d/%m/%Y %H:%M")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 40px;
      color: #1a1a1a;
      line-height: 1.6;
    }}
    .header {{
      border-bottom: 3px solid #e85d04;
      padding-bottom: 16px;
      margin-bottom: 24px;
    }}
    .header h1 {{
      color: #e85d04;
      margin: 0 0 4px 0;
      font-size: 22px;
    }}
    .meta {{
      color: #666;
      font-size: 13px;
    }}
    .section-label {{
      font-size: 11px;
      font-weight: bold;
      color: #888;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 6px;
    }}
    .question-box {{
      background: #f5f5f5;
      border-left: 4px solid #e85d04;
      padding: 12px 16px;
      border-radius: 4px;
      margin-bottom: 24px;
      font-size: 15px;
    }}
    .answer-box {{
      background: #fff;
      border: 1px solid #e0e0e0;
      border-radius: 6px;
      padding: 20px;
      font-size: 14px;
      margin-bottom: 24px;
    }}
    .source {{
      display: inline-block;
      background: #e8f4fd;
      color: #1a6fa0;
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 12px;
      margin: 2px 4px 2px 0;
    }}
    .footer {{
      border-top: 1px solid #eee;
      padding-top: 12px;
      font-size: 11px;
      color: #aaa;
      margin-top: 32px;
    }}
  </style>
</head>
<body>
  <div class="header">
    <h1>FireManager — Relatório de Análise N3</h1>
    <p class="meta">Gerado em {created} &nbsp;|&nbsp; Analista: IA (Claude)</p>
  </div>

  <div class="section-label">Pergunta do analista</div>
  <div class="question-box">{session.question}</div>

  <div class="section-label">Análise</div>
  <div class="answer-box">{answer_html}</div>

  <div class="section-label">Fontes consultadas</div>
  <div style="margin-bottom: 24px">{sources_html if sources_html else '<span style="color:#aaa">Nenhuma fonte registrada</span>'}</div>

  <div class="footer">
    FireManager v0.1.0 &nbsp;|&nbsp; Sessão ID: {session.id}
  </div>
</body>
</html>"""
