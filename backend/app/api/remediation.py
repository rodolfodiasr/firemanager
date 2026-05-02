import io
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_module_reviewer, require_reviewer

_require_remediation = require_module_reviewer("remediation")
from app.database import get_db
from app.schemas.remediation import (
    CommandEdit,
    CommandReview,
    CorrectiveRequest,
    RemediationCommandRead,
    RemediationPlanRead,
    RemediationRequest,
    ReviewerComment,
)
from app.services import remediation_service

router = APIRouter()


@router.post("", response_model=RemediationPlanRead, status_code=201)
async def create_plan(
    data: RemediationRequest,
    ctx:  Annotated[TenantContext, Depends(_require_remediation)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> RemediationPlanRead:
    try:
        plan = await remediation_service.generate_plan(
            db=db,
            tenant_id=ctx.tenant.id,
            server_id=data.server_id,
            request=data.request,
            session_id=data.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar plano: {exc}")
    return RemediationPlanRead.model_validate(plan)


@router.get("", response_model=list[RemediationPlanRead])
async def list_plans(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[RemediationPlanRead]:
    plans = await remediation_service.list_plans(db, tenant_id=ctx.tenant.id)
    return [RemediationPlanRead.model_validate(p) for p in plans]


@router.get("/{plan_id}", response_model=RemediationPlanRead)
async def get_plan(
    plan_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> RemediationPlanRead:
    plan = await remediation_service.get_plan(db, tenant_id=ctx.tenant.id, plan_id=plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    return RemediationPlanRead.model_validate(plan)


@router.patch("/{plan_id}/commands/{command_id}", response_model=RemediationCommandRead)
async def update_command(
    plan_id: UUID,
    command_id: UUID,
    body: CommandEdit,
    ctx: Annotated[TenantContext, Depends(_require_remediation)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RemediationCommandRead:
    try:
        cmd = await remediation_service.update_command(
            db, ctx.tenant.id, plan_id, command_id,
            new_command=body.command,
            new_description=body.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RemediationCommandRead.model_validate(cmd)


@router.post("/{plan_id}/retry", response_model=RemediationPlanRead, status_code=201)
async def retry_plan(
    plan_id: UUID,
    ctx: Annotated[TenantContext, Depends(_require_remediation)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RemediationPlanRead:
    try:
        plan = await remediation_service.retry_plan(db, ctx.tenant.id, plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao retentar: {exc}")
    return RemediationPlanRead.model_validate(plan)


@router.post("/{plan_id}/commands/{command_id}/approve", response_model=dict)
async def approve_command(
    plan_id: UUID,
    command_id: UUID,
    ctx: Annotated[TenantContext, Depends(_require_remediation)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        cmd = await remediation_service.approve_command(db, ctx.tenant.id, plan_id, command_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": str(cmd.id), "status": cmd.status.value}


@router.post("/{plan_id}/commands/{command_id}/reject", response_model=dict)
async def reject_command(
    plan_id: UUID,
    command_id: UUID,
    body: CommandReview,
    ctx: Annotated[TenantContext, Depends(_require_remediation)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        cmd = await remediation_service.reject_command(
            db, ctx.tenant.id, plan_id, command_id, comment=body.comment
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": str(cmd.id), "status": cmd.status.value}


@router.post("/{plan_id}/execute", response_model=RemediationPlanRead)
async def execute_plan(
    plan_id: UUID,
    ctx: Annotated[TenantContext, Depends(_require_remediation)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> RemediationPlanRead:
    try:
        plan = await remediation_service.execute_plan(db, ctx.tenant.id, plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao executar: {exc}")
    return RemediationPlanRead.model_validate(plan)


@router.post("/{plan_id}/rollback", response_model=RemediationPlanRead, status_code=201)
async def create_rollback_plan(
    plan_id: UUID,
    ctx: Annotated[TenantContext, Depends(_require_remediation)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> RemediationPlanRead:
    try:
        plan = await remediation_service.create_rollback_plan(db, ctx.tenant.id, plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao criar plano de rollback: {exc}")
    return RemediationPlanRead.model_validate(plan)


@router.post("/{plan_id}/corrective", response_model=RemediationPlanRead, status_code=201)
async def corrective_plan(
    plan_id: UUID,
    body: CorrectiveRequest,
    ctx: Annotated[TenantContext, Depends(_require_remediation)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> RemediationPlanRead:
    try:
        plan = await remediation_service.corrective_plan(
            db, ctx.tenant.id, plan_id, observation=body.observation
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar plano corretivo: {exc}")
    return RemediationPlanRead.model_validate(plan)


@router.get("/{plan_id}/export")
async def export_pdf(
    plan_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    plan = await remediation_service.get_plan(db, ctx.tenant.id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado")

    from sqlalchemy import select as sa_select
    from app.models.server import Server

    srv = await db.execute(sa_select(Server).where(Server.id == plan.server_id))
    server = srv.scalar_one_or_none()
    server_name = server.name if server else str(plan.server_id)
    server_host = server.host if server else ""

    try:
        from weasyprint import HTML
        html = _build_execution_pdf(plan, server_name, server_host)
        pdf_bytes = HTML(string=html).write_pdf()
        fname = f"remediation_{plan.created_at.strftime('%Y%m%d_%H%M')}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {exc}")


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: UUID,
    ctx: Annotated[TenantContext, Depends(_require_remediation)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    plan = await remediation_service.get_plan(db, ctx.tenant.id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    await db.delete(plan)
    await db.flush()


def _build_execution_pdf(plan, server_name: str, server_host: str) -> str:
    import html as html_lib

    STATUS_COLOR = {
        "completed": "#38a169",
        "failed":    "#e53e3e",
        "skipped":   "#a0aec0",
        "executing": "#805ad5",
        "pending":   "#d69e2e",
        "approved":  "#3182ce",
        "rejected":  "#e53e3e",
    }
    PLAN_STATUS_LABEL = {
        "pending_approval": "Aguardando aprovação",
        "approved":         "Aprovado",
        "executing":        "Executando",
        "completed":        "Concluído",
        "partial":          "Parcial",
        "rejected":         "Rejeitado",
    }
    plan_status = plan.status.value if hasattr(plan.status, "value") else str(plan.status)
    status_color = STATUS_COLOR.get(plan_status, "#718096")
    status_label = PLAN_STATUS_LABEL.get(plan_status, plan_status)
    created = plan.created_at.strftime("%d/%m/%Y %H:%M")
    reviewed = plan.reviewed_at.strftime("%d/%m/%Y %H:%M") if plan.reviewed_at else "—"

    cmds = sorted(plan.commands, key=lambda c: c.order)
    total = len(cmds)
    completed = sum(1 for c in cmds if c.status.value == "completed")
    failed    = sum(1 for c in cmds if c.status.value == "failed")
    skipped   = sum(1 for c in cmds if c.status.value == "skipped")

    rows = ""
    for cmd in cmds:
        s = cmd.status.value if hasattr(cmd.status, "value") else str(cmd.status)
        s_color = STATUS_COLOR.get(s, "#718096")
        output_esc = html_lib.escape(cmd.output or "(sem saída)")
        cmd_esc    = html_lib.escape(cmd.command)
        exec_time  = cmd.executed_at.strftime("%d/%m %H:%M:%S") if cmd.executed_at else "—"
        rows += f"""
        <tr>
          <td style="text-align:center;color:#888;font-size:12px">{cmd.order}</td>
          <td style="font-size:13px">{html_lib.escape(cmd.description)}</td>
          <td style="font-size:11px"><pre style="margin:0;white-space:pre-wrap;word-break:break-all;background:#1a1a2e;color:#a8ff78;padding:6px 8px;border-radius:4px;font-family:monospace">{cmd_esc}</pre></td>
          <td style="text-align:center;font-size:11px;font-weight:bold;color:{s_color};text-transform:uppercase">{s}</td>
          <td style="font-size:11px;color:#888">{exec_time}</td>
        </tr>
        <tr>
          <td colspan="5" style="padding:0 0 12px 36px">
            <pre style="margin:0;white-space:pre-wrap;word-break:break-all;font-size:11px;background:#f7f7f7;border:1px solid #e0e0e0;padding:8px 12px;border-radius:4px;color:#333;font-family:monospace;{'border-left:3px solid #e53e3e' if s=='failed' else ''}">{output_esc}</pre>
          </td>
        </tr>"""

    summary_esc = html_lib.escape(plan.summary or "").replace("\n", "<br>")
    request_esc = html_lib.escape(plan.request)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; color: #1a1a1a; line-height: 1.5; font-size: 14px; }}
    .header {{ border-bottom: 3px solid #e85d04; padding-bottom: 16px; margin-bottom: 24px; }}
    .header h1 {{ color: #e85d04; margin: 0 0 4px 0; font-size: 22px; }}
    .meta {{ color: #666; font-size: 13px; }}
    .badge {{ display: inline-block; font-size: 12px; font-weight: bold; padding: 3px 10px;
      border-radius: 10px; color: white; background: {status_color}; }}
    .counters {{ display: flex; gap: 32px; margin: 16px 0 24px; }}
    .counter .num {{ font-size: 28px; font-weight: bold; }}
    .counter .lbl {{ font-size: 11px; color: #888; text-transform: uppercase; }}
    .section-label {{ font-size: 11px; font-weight: bold; color: #888; text-transform: uppercase;
      letter-spacing: 0.05em; margin: 20px 0 8px; border-bottom: 1px solid #eee; padding-bottom: 4px; }}
    .summary-box {{ background: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 6px;
      padding: 14px 16px; font-size: 13px; margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ background: #f0f0f0; text-align: left; padding: 8px; font-size: 11px; color: #555;
      text-transform: uppercase; border-bottom: 2px solid #ddd; }}
    td {{ padding: 8px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }}
    .footer {{ border-top: 1px solid #eee; padding-top: 12px; font-size: 11px; color: #aaa; margin-top: 32px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>FireManager — Relatório de Remediação</h1>
    <p class="meta">
      Servidor: <strong>{html_lib.escape(server_name)}</strong> ({html_lib.escape(server_host)}) &nbsp;|&nbsp;
      Criado em: {created} &nbsp;|&nbsp;
      Executado em: {reviewed} &nbsp;|&nbsp;
      Status: <span class="badge">{status_label}</span>
    </p>
  </div>

  <div class="section-label">Solicitação</div>
  <div class="summary-box"><strong>{request_esc}</strong></div>

  <div class="section-label">Resumo do Plano</div>
  <div class="summary-box">{summary_esc}</div>

  <div class="counters">
    <div class="counter"><div class="num">{total}</div><div class="lbl">Total</div></div>
    <div class="counter"><div class="num" style="color:#38a169">{completed}</div><div class="lbl">Concluídos</div></div>
    <div class="counter"><div class="num" style="color:#e53e3e">{failed}</div><div class="lbl">Falharam</div></div>
    <div class="counter"><div class="num" style="color:#a0aec0">{skipped}</div><div class="lbl">Pulados</div></div>
  </div>

  <div class="section-label">Log de Execução</div>
  <table>
    <tr><th style="width:36px">#</th><th>Descrição</th><th>Comando</th><th style="width:90px">Status</th><th style="width:100px">Executado</th></tr>
    {rows}
  </table>

  <div class="footer">
    FireManager v0.1.0 &nbsp;|&nbsp; Plano ID: {plan.id}
  </div>
</body>
</html>"""
