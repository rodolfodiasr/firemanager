import io
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.schemas.compliance import (
    ComplianceGenerateRequest,
    ComplianceReportRead,
    ComplianceReportSummary,
)
from app.services import compliance_service

router = APIRouter()


@router.post("", response_model=ComplianceReportRead, status_code=201)
async def generate_report(
    data: ComplianceGenerateRequest,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> ComplianceReportRead:
    try:
        report = await compliance_service.generate_report(
            db=db,
            tenant_id=ctx.tenant.id,
            server_id=data.server_id,
            policy_id=data.policy_id,
            force_source=data.force_source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar relatório: {exc}")
    return ComplianceReportRead.model_validate(report)


@router.get("", response_model=list[ComplianceReportSummary])
async def list_reports(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[ComplianceReportSummary]:
    reports = await compliance_service.list_reports(db, tenant_id=ctx.tenant.id)
    return [ComplianceReportSummary.model_validate(r) for r in reports]


@router.get("/{report_id}", response_model=ComplianceReportRead)
async def get_report(
    report_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> ComplianceReportRead:
    report = await compliance_service.get_report(db, ctx.tenant.id, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    return ComplianceReportRead.model_validate(report)


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    report = await compliance_service.get_report(db, ctx.tenant.id, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    await db.delete(report)
    await db.flush()


@router.get("/{report_id}/export-pdf")
async def export_pdf(
    report_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    report = await compliance_service.get_report(db, ctx.tenant.id, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    # Resolve server name for PDF
    from app.models.server import Server
    from sqlalchemy import select as sa_select

    srv_result = await db.execute(sa_select(Server).where(Server.id == report.server_id))
    server = srv_result.scalar_one_or_none()
    server_name = server.name if server else str(report.server_id)

    try:
        from weasyprint import HTML

        html = _build_pdf_html(report, server_name)
        pdf_bytes = HTML(string=html).write_pdf()
        filename = f"compliance_{report.created_at.strftime('%Y%m%d_%H%M')}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {exc}")


def _build_pdf_html(report, server_name: str) -> str:
    from app.models.compliance import ComplianceReport

    score_color = (
        "#e53e3e" if report.score_pct < 50
        else "#d69e2e" if report.score_pct < 75
        else "#38a169"
    )

    source_label = "Wazuh SCA (agente)" if report.source == "wazuh" else "SSH (snapshot)"
    created = report.created_at.strftime("%d/%m/%Y %H:%M")

    failed_controls = [c for c in (report.controls or []) if c.get("result") == "failed"][:20]
    controls_rows = ""
    for ctrl in failed_controls:
        risk = ctrl.get("risk_level", "medium")
        risk_color = {"critical": "#e53e3e", "high": "#dd6b20", "medium": "#d69e2e", "low": "#718096"}.get(risk, "#718096")
        controls_rows += f"""
        <tr>
          <td style="color:#555;font-size:11px">{ctrl.get('control_id','')}</td>
          <td style="font-size:12px">{ctrl.get('title','')}</td>
          <td style="color:{risk_color};font-weight:bold;font-size:11px;text-transform:uppercase">{risk}</td>
          <td style="font-size:11px;color:#333">{ctrl.get('remediation','')[:120]}</td>
        </tr>"""

    recs_html = ""
    for rec in (report.ai_recommendations or [])[:10]:
        recs_html += f"""
        <div class="rec-item">
          <span class="rec-priority">#{rec.get('priority','')}</span>
          <strong>{rec.get('title','')}</strong>
          <p style="margin:4px 0 4px 0;color:#555;font-size:13px">{rec.get('description','')}</p>
          <pre class="code">{rec.get('remediation_steps','')}</pre>
        </div>"""

    ai_summary_html = (report.ai_summary or "").replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; color: #1a1a1a; line-height: 1.5; }}
    .header {{ border-bottom: 3px solid #e85d04; padding-bottom: 16px; margin-bottom: 24px; }}
    .header h1 {{ color: #e85d04; margin: 0 0 4px 0; font-size: 22px; }}
    .meta {{ color: #666; font-size: 13px; }}
    .score-box {{ display: inline-block; background: {score_color}; color: white; font-size: 36px;
      font-weight: bold; padding: 12px 24px; border-radius: 8px; margin: 8px 0; }}
    .counters {{ display: flex; gap: 24px; margin: 12px 0 24px; }}
    .counter {{ text-align: center; }}
    .counter .num {{ font-size: 24px; font-weight: bold; }}
    .counter .lbl {{ font-size: 11px; color: #888; text-transform: uppercase; }}
    .section-label {{ font-size: 11px; font-weight: bold; color: #888; text-transform: uppercase;
      letter-spacing: 0.05em; margin: 20px 0 8px; }}
    .summary-box {{ background: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 6px;
      padding: 16px; font-size: 14px; margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 24px; }}
    th {{ background: #f0f0f0; text-align: left; padding: 8px; font-size: 11px; color: #555;
      text-transform: uppercase; }}
    td {{ padding: 7px 8px; border-bottom: 1px solid #eee; vertical-align: top; }}
    .rec-item {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 6px;
      padding: 12px 16px; margin-bottom: 10px; }}
    .rec-priority {{ display: inline-block; background: #e85d04; color: white; font-size: 11px;
      font-weight: bold; padding: 1px 6px; border-radius: 10px; margin-right: 6px; }}
    .code {{ background: #1a1a2e; color: #a8ff78; font-size: 11px; padding: 8px 12px;
      border-radius: 4px; overflow: hidden; margin: 6px 0 0; font-family: monospace; }}
    .footer {{ border-top: 1px solid #eee; padding-top: 12px; font-size: 11px; color: #aaa; margin-top: 32px; }}
    .badge {{ display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 10px;
      background: #e8f4fd; color: #1a6fa0; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>FireManager — Relatório de Conformidade CIS Benchmark</h1>
    <p class="meta">
      Servidor: <strong>{server_name}</strong> &nbsp;|&nbsp;
      Política: <strong>{report.policy_name}</strong> &nbsp;|&nbsp;
      Fonte: <span class="badge">{source_label}</span> &nbsp;|&nbsp;
      Gerado em {created}
    </p>
  </div>

  <div class="section-label">Score de Conformidade</div>
  <div class="score-box">{report.score_pct:.1f}%</div>
  <div class="counters">
    <div class="counter"><div class="num" style="color:#38a169">{report.passed}</div><div class="lbl">Passou</div></div>
    <div class="counter"><div class="num" style="color:#e53e3e">{report.failed}</div><div class="lbl">Falhou</div></div>
    <div class="counter"><div class="num" style="color:#718096">{report.not_applicable}</div><div class="lbl">N/A</div></div>
    <div class="counter"><div class="num">{report.total_checks}</div><div class="lbl">Total</div></div>
  </div>

  <div class="section-label">Resumo Executivo</div>
  <div class="summary-box">{ai_summary_html}</div>

  <div class="section-label">Controles Reprovados (top 20)</div>
  <table>
    <tr><th>ID</th><th>Controle</th><th>Risco</th><th>Remediação</th></tr>
    {controls_rows if controls_rows else '<tr><td colspan="4" style="color:#aaa;text-align:center">Nenhuma falha encontrada</td></tr>'}
  </table>

  <div class="section-label">Recomendações Prioritárias</div>
  {recs_html if recs_html else '<p style="color:#aaa;font-size:13px">Nenhuma recomendação gerada.</p>'}

  <div class="footer">
    FireManager v0.1.0 &nbsp;|&nbsp; Relatório ID: {report.id}
  </div>
</body>
</html>"""
