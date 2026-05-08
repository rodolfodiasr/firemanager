"""Fase 24 — Executive dashboard and PDF report service."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import LifecycleAction, IdentityUser, ActionStatus, ActionType
from app.models.alert import AlertEvent


async def get_security_posture(db: AsyncSession, tenant_id) -> dict:
    """Aggregate security posture metrics for the executive dashboard."""
    from app.models.server import Server
    from app.models.database_connector import DatabaseConnector

    # Identity metrics
    total_users = (await db.execute(
        select(func.count()).select_from(IdentityUser).where(IdentityUser.tenant_id == tenant_id)
    )).scalar_one()

    orphan_count = (await db.execute(
        select(func.count()).select_from(IdentityUser).where(
            IdentityUser.tenant_id == tenant_id,
            IdentityUser.is_enabled.is_(False),
        )
    )).scalar_one()

    # Lifecycle actions last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    offboards_completed = (await db.execute(
        select(func.count()).select_from(LifecycleAction).where(
            LifecycleAction.tenant_id == tenant_id,
            LifecycleAction.action_type == ActionType.offboard,
            LifecycleAction.status == ActionStatus.completed,
            LifecycleAction.created_at >= thirty_days_ago,
        )
    )).scalar_one()

    offboards_pending = (await db.execute(
        select(func.count()).select_from(LifecycleAction).where(
            LifecycleAction.tenant_id == tenant_id,
            LifecycleAction.status.in_([ActionStatus.pending_discovery, ActionStatus.pending_approval]),
        )
    )).scalar_one()

    onboards_completed = (await db.execute(
        select(func.count()).select_from(LifecycleAction).where(
            LifecycleAction.tenant_id == tenant_id,
            LifecycleAction.action_type == ActionType.onboard,
            LifecycleAction.status == ActionStatus.completed,
            LifecycleAction.created_at >= thirty_days_ago,
        )
    )).scalar_one()

    # Servers and infrastructure
    server_count = (await db.execute(
        select(func.count()).select_from(Server).where(Server.tenant_id == tenant_id)
    )).scalar_one()

    db_count = (await db.execute(
        select(func.count()).select_from(DatabaseConnector).where(DatabaseConnector.tenant_id == tenant_id)
    )).scalar_one()

    # Alerts last 7 days
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_alerts = (await db.execute(
        select(func.count()).select_from(AlertEvent).where(
            AlertEvent.tenant_id == tenant_id,
            AlertEvent.created_at >= seven_days_ago,
        )
    )).scalar_one()

    critical_alerts = (await db.execute(
        select(func.count()).select_from(AlertEvent).where(
            AlertEvent.tenant_id == tenant_id,
            AlertEvent.severity == "critical",
            AlertEvent.created_at >= seven_days_ago,
        )
    )).scalar_one()

    # Risk score (0–100, lower is better)
    risk_score = _calculate_risk_score(orphan_count, total_users, critical_alerts, offboards_pending)

    # Recent events timeline
    recent_actions = (await db.execute(
        select(LifecycleAction)
        .where(LifecycleAction.tenant_id == tenant_id)
        .order_by(LifecycleAction.created_at.desc())
        .limit(10)
    )).scalars().all()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "risk_score": risk_score,
        "identity": {
            "total_users": total_users,
            "orphan_accounts": orphan_count,
            "orphan_percentage": round(orphan_count / total_users * 100, 1) if total_users else 0,
        },
        "lifecycle_30d": {
            "offboards_completed": offboards_completed,
            "onboards_completed": onboards_completed,
            "pending_actions": offboards_pending,
        },
        "infrastructure": {
            "servers": server_count,
            "databases": db_count,
        },
        "alerts_7d": {
            "total": recent_alerts,
            "critical": critical_alerts,
        },
        "recent_actions": [
            {
                "id": str(a.id),
                "action_type": a.action_type,
                "target_username": a.target_username,
                "status": a.status,
                "created_at": a.created_at.isoformat(),
            }
            for a in recent_actions
        ],
    }


def _calculate_risk_score(orphan_count: int, total_users: int, critical_alerts: int, pending_offboards: int) -> int:
    score = 0
    if total_users > 0:
        orphan_pct = orphan_count / total_users
        score += min(40, int(orphan_pct * 200))
    score += min(30, critical_alerts * 5)
    score += min(30, pending_offboards * 10)
    return min(100, score)


async def generate_pdf_report(db: AsyncSession, tenant_id, period_days: int = 30) -> bytes:
    """Generate an executive PDF report using WeasyPrint."""
    posture = await get_security_posture(db, tenant_id)

    # Fetch tenant name
    from sqlalchemy import text
    row = (await db.execute(
        text("SELECT name FROM tenants WHERE id = :tid"),
        {"tid": str(tenant_id)},
    )).first()
    tenant_name = row[0] if row else "Desconhecido"

    html = _build_report_html(tenant_name, posture, period_days)

    from weasyprint import HTML
    import asyncio
    pdf_bytes = await asyncio.to_thread(lambda: HTML(string=html).write_pdf())
    return pdf_bytes


def _build_report_html(tenant_name: str, posture: dict, period_days: int) -> str:
    risk = posture["risk_score"]
    risk_color = "#22c55e" if risk < 30 else ("#f59e0b" if risk < 60 else "#ef4444")
    risk_label = "BAIXO" if risk < 30 else ("MÉDIO" if risk < 60 else "ALTO")

    ident = posture["identity"]
    lc = posture["lifecycle_30d"]
    infra = posture["infrastructure"]
    alerts = posture["alerts_7d"]

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; color: #1f2937; margin: 0; padding: 0; }}
  .cover {{ background: #1e293b; color: white; padding: 60px 48px; }}
  .cover h1 {{ font-size: 32px; margin: 0 0 8px; }}
  .cover .subtitle {{ font-size: 16px; color: #94a3b8; }}
  .section {{ padding: 32px 48px; border-bottom: 1px solid #e5e7eb; }}
  .section h2 {{ font-size: 20px; color: #1e40af; margin-bottom: 16px; }}
  .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }}
  .metric {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; text-align: center; }}
  .metric .value {{ font-size: 36px; font-weight: bold; color: #1e40af; }}
  .metric .label {{ font-size: 13px; color: #64748b; margin-top: 4px; }}
  .risk-badge {{ display: inline-block; padding: 8px 20px; border-radius: 24px; font-weight: bold; font-size: 18px; color: white; background: {risk_color}; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #1e293b; color: white; padding: 10px; text-align: left; font-size: 13px; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #f1f5f9; font-size: 13px; }}
  tr:nth-child(even) {{ background: #f8fafc; }}
  .footer {{ padding: 24px 48px; font-size: 12px; color: #94a3b8; text-align: center; }}
</style>
</head>
<body>
<div class="cover">
  <div style="font-size:13px; color:#64748b; margin-bottom:12px;">RELATÓRIO EXECUTIVO DE SEGURANÇA</div>
  <h1>{tenant_name}</h1>
  <div class="subtitle">Período: últimos {period_days} dias &nbsp;|&nbsp; Gerado em: {posture['generated_at'][:10]}</div>
</div>

<div class="section">
  <h2>Postura de Segurança</h2>
  <p>Score de Risco: <span class="risk-badge">{risk_label} ({risk}/100)</span></p>
  <p style="color:#64748b; font-size:14px;">Calculado com base em contas órfãs, alertas críticos e offboardings pendentes.</p>
  <div class="metrics">
    <div class="metric"><div class="value">{ident['total_users']}</div><div class="label">Usuários Ativos</div></div>
    <div class="metric"><div class="value">{ident['orphan_accounts']}</div><div class="label">Contas Órfãs</div></div>
    <div class="metric"><div class="value">{ident['orphan_percentage']}%</div><div class="label">% Contas Inativas</div></div>
  </div>
</div>

<div class="section">
  <h2>Ciclo de Vida de Identidades — {period_days} dias</h2>
  <div class="metrics">
    <div class="metric"><div class="value">{lc['offboards_completed']}</div><div class="label">Offboardings Concluídos</div></div>
    <div class="metric"><div class="value">{lc['onboards_completed']}</div><div class="label">Onboardings Concluídos</div></div>
    <div class="metric"><div class="value">{lc['pending_actions']}</div><div class="label">Ações Pendentes</div></div>
  </div>
</div>

<div class="section">
  <h2>Infraestrutura & Alertas</h2>
  <div class="metrics">
    <div class="metric"><div class="value">{infra['servers']}</div><div class="label">Servidores Monitorados</div></div>
    <div class="metric"><div class="value">{infra['databases']}</div><div class="label">Bancos de Dados</div></div>
    <div class="metric"><div class="value">{alerts['critical']}</div><div class="label">Alertas Críticos (7d)</div></div>
  </div>
</div>

<div class="section">
  <h2>Ações Recentes</h2>
  <table>
    <tr><th>Data</th><th>Tipo</th><th>Usuário</th><th>Status</th></tr>
    {''.join(f"<tr><td>{a['created_at'][:10]}</td><td>{a['action_type']}</td><td>{a['target_username']}</td><td>{a['status']}</td></tr>" for a in posture['recent_actions'])}
  </table>
</div>

<div class="footer">
  Gerado automaticamente pelo FireManager SecOps &nbsp;|&nbsp; Confidencial — uso interno
</div>
</body>
</html>"""
