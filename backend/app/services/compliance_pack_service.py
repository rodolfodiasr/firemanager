"""Service — F30 Compliance Pack seeds and scoring (CIS/PCI-DSS/BACEN/LGPD).

This service works on top of the existing compliance_packs_service using the
CompliancePack + CompliancePackAssessment ORM models from migration 0061.
It provides the seed functions, score calculation and report generation
requested by F30.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.compliance_enterprise import (
    BcdrPlan,
    CompliancePack,
    CompliancePackAssessment,
    CompliancePackControl,
    SlaConfig,
)

# ── Control definitions ───────────────────────────────────────────────────────

CIS_CONTROLS: list[dict] = [
    {"control_id": "CIS-1.1", "title": "Inventário de Ativos de Hardware", "category": "Inventário", "severity": "high"},
    {"control_id": "CIS-1.2", "title": "Inventário de Ativos de Software", "category": "Inventário", "severity": "high"},
    {"control_id": "CIS-2.1", "title": "Configurações Seguras para Hardware e Software", "category": "Configuração", "severity": "critical"},
    {"control_id": "CIS-3.1", "title": "Proteção de Dados em Repouso", "category": "Dados", "severity": "critical"},
    {"control_id": "CIS-4.1", "title": "Controle de Acesso Privilegiado", "category": "Acesso", "severity": "critical"},
    {"control_id": "CIS-5.1", "title": "Gestão de Contas de Usuário", "category": "Acesso", "severity": "high"},
    {"control_id": "CIS-6.1", "title": "Gestão de Log e Monitoramento", "category": "Monitoramento", "severity": "high"},
    {"control_id": "CIS-7.1", "title": "Proteção de Email e Web", "category": "Proteção", "severity": "medium"},
    {"control_id": "CIS-8.1", "title": "Defesa contra Malware", "category": "Proteção", "severity": "critical"},
    {"control_id": "CIS-9.1", "title": "Limitação e Controle de Portas de Rede", "category": "Rede", "severity": "high"},
    {"control_id": "CIS-10.1", "title": "Capacidade de Recuperação de Dados", "category": "Resiliência", "severity": "critical"},
    {"control_id": "CIS-11.1", "title": "Configuração Segura de Dispositivos de Rede", "category": "Rede", "severity": "critical"},
    {"control_id": "CIS-12.1", "title": "Proteção de Fronteira de Rede", "category": "Rede", "severity": "high"},
    {"control_id": "CIS-13.1", "title": "Proteção de Dados", "category": "Dados", "severity": "critical"},
    {"control_id": "CIS-14.1", "title": "Acesso Controlado com Base na Necessidade", "category": "Acesso", "severity": "high"},
]

PCI_DSS_CONTROLS: list[dict] = [
    {"control_id": "PCI-1.1", "title": "Instalar e manter firewall", "category": "Rede", "severity": "critical"},
    {"control_id": "PCI-1.2", "title": "Proibir defaults de vendor para senhas", "category": "Configuração", "severity": "critical"},
    {"control_id": "PCI-3.1", "title": "Proteger dados de portadores de cartão armazenados", "category": "Dados", "severity": "critical"},
    {"control_id": "PCI-4.1", "title": "Criptografar transmissão de dados sensíveis", "category": "Criptografia", "severity": "critical"},
    {"control_id": "PCI-5.1", "title": "Usar e atualizar software antivírus", "category": "Proteção", "severity": "high"},
    {"control_id": "PCI-6.1", "title": "Desenvolver sistemas e apps seguros", "category": "Desenvolvimento", "severity": "high"},
    {"control_id": "PCI-7.1", "title": "Restringir acesso por necessidade de negócio", "category": "Acesso", "severity": "high"},
    {"control_id": "PCI-8.1", "title": "Identificar e autenticar acesso a componentes", "category": "Acesso", "severity": "critical"},
    {"control_id": "PCI-9.1", "title": "Restringir acesso físico aos dados", "category": "Físico", "severity": "high"},
    {"control_id": "PCI-10.1", "title": "Rastrear e monitorar acesso a recursos de rede", "category": "Monitoramento", "severity": "critical"},
    {"control_id": "PCI-11.1", "title": "Testar sistemas e processos de segurança regularmente", "category": "Testes", "severity": "high"},
    {"control_id": "PCI-12.1", "title": "Manter política de segurança da informação", "category": "Governança", "severity": "medium"},
]

BACEN_4658_CONTROLS: list[dict] = [
    {"control_id": "BACEN-Art3", "title": "Política de Segurança Cibernética documentada e aprovada", "category": "Governança", "severity": "critical"},
    {"control_id": "BACEN-Art4", "title": "Programa de capacitação e conscientização", "category": "Treinamento", "severity": "high"},
    {"control_id": "BACEN-Art6", "title": "Plano de Continuidade de Negócios (PCN)", "category": "BC/DR", "severity": "critical"},
    {"control_id": "BACEN-Art7", "title": "Relatório anual de segurança cibernética ao Conselho", "category": "Governança", "severity": "high"},
    {"control_id": "BACEN-Art8", "title": "Contratação de processamento de dados no Brasil", "category": "Soberania", "severity": "critical"},
    {"control_id": "BACEN-Art11", "title": "Notificação ao BACEN de incidentes relevantes", "category": "Incidentes", "severity": "critical"},
    {"control_id": "BACEN-Circ3909-Art2", "title": "Testes anuais do plano de continuidade", "category": "BC/DR", "severity": "high"},
    {"control_id": "BACEN-Circ3909-Art3", "title": "Monitoramento contínuo dos sistemas", "category": "Monitoramento", "severity": "critical"},
]

LGPD_CONTROLS: list[dict] = [
    {"control_id": "LGPD-Art6", "title": "Base legal para tratamento de dados pessoais", "category": "Base Legal", "severity": "critical"},
    {"control_id": "LGPD-Art7", "title": "Consentimento explícito para dados pessoais", "category": "Consentimento", "severity": "critical"},
    {"control_id": "LGPD-Art9", "title": "Garantia de direitos do titular", "category": "Direitos", "severity": "high"},
    {"control_id": "LGPD-Art13", "title": "Anonimização de dados para fins estatísticos", "category": "Privacidade", "severity": "medium"},
    {"control_id": "LGPD-Art46", "title": "Medidas de segurança técnicas e administrativas", "category": "Segurança", "severity": "critical"},
    {"control_id": "LGPD-Art48", "title": "Comunicação de incidentes à ANPD e titulares", "category": "Incidentes", "severity": "critical"},
    {"control_id": "LGPD-Art50", "title": "Programa de Governança em Privacidade", "category": "Governança", "severity": "high"},
    {"control_id": "LGPD-Art55-A", "title": "Nomeação de Encarregado (DPO)", "category": "Governança", "severity": "high"},
]

_PACK_MAP: dict[str, dict] = {
    "cis_benchmark": {
        "name": "CIS Controls v8",
        "framework": "cis_benchmark",
        "version": "v8",
        "description": "Center for Internet Security Controls v8 — 15 controles essenciais.",
        "controls": CIS_CONTROLS,
    },
    "pci_dss": {
        "name": "PCI-DSS v4.0",
        "framework": "pci_dss",
        "version": "v4.0",
        "description": "Payment Card Industry Data Security Standard v4.0 — 12 requisitos.",
        "controls": PCI_DSS_CONTROLS,
    },
    "bacen_4658": {
        "name": "BACEN Resolução 4.658",
        "framework": "bacen_4658",
        "version": "Res. 4.658",
        "description": "Política de segurança cibernética para instituições financeiras (BACEN CMN 4.658).",
        "controls": BACEN_4658_CONTROLS,
    },
    "lgpd": {
        "name": "LGPD — Lei 13.709/2018",
        "framework": "lgpd",
        "version": "Lei 13.709/2018",
        "description": "Lei Geral de Proteção de Dados — 8 controles de conformidade.",
        "controls": LGPD_CONTROLS,
    },
}

# Valid statuses for controls in assessment findings
COMPLIANT_STATUSES = {"compliant"}
NON_APPLICABLE_STATUSES = {"not_applicable", "na"}


# ── Pack seeding ──────────────────────────────────────────────────────────────

async def seed_pack_by_type(db: AsyncSession, pack_type: str) -> CompliancePack:
    """Create (or return existing) global pack for the given pack_type.

    Returns the CompliancePack instance with all controls loaded.
    """
    pack_def = _PACK_MAP.get(pack_type)
    if not pack_def:
        raise ValueError(f"pack_type inválido: {pack_type}. Valores aceitos: {list(_PACK_MAP)}")

    # Check if pack already exists by framework
    result = await db.execute(
        select(CompliancePack)
        .where(CompliancePack.framework == pack_def["framework"])
        .options(selectinload(CompliancePack.controls))
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    pack = CompliancePack(
        name=pack_def["name"],
        framework=pack_def["framework"],
        version=pack_def["version"],
        description=pack_def["description"],
        is_builtin=True,
        is_active=True,
    )
    db.add(pack)
    await db.flush()

    for i, ctrl_def in enumerate(pack_def["controls"]):
        ctrl = CompliancePackControl(
            pack_id=pack.id,
            control_id=ctrl_def["control_id"],
            title=ctrl_def["title"],
            category=ctrl_def.get("category"),
            severity=ctrl_def.get("severity", "medium"),
            verification_type="manual",
            evidence_hint=None,
            sort_order=i,
        )
        db.add(ctrl)

    await db.commit()

    # Reload with controls
    result2 = await db.execute(
        select(CompliancePack)
        .where(CompliancePack.id == pack.id)
        .options(selectinload(CompliancePack.controls))
    )
    return result2.scalar_one()


# ── Score calculation ─────────────────────────────────────────────────────────

def calculate_score_from_findings(findings: list[dict]) -> int:
    """Score = (compliant_count / total_non_na_count) * 100.

    Returns integer 0-100.
    """
    if not findings:
        return 0
    non_na = [f for f in findings if f.get("status") not in NON_APPLICABLE_STATUSES]
    if not non_na:
        return 0
    compliant = sum(1 for f in non_na if f.get("status") in COMPLIANT_STATUSES)
    return round((compliant / len(non_na)) * 100)


# ── Pack summary (per tenant) ─────────────────────────────────────────────────

async def get_pack_summary(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    """List all assessments for the tenant grouped by framework, with score."""
    result = await db.execute(
        select(CompliancePackAssessment)
        .where(CompliancePackAssessment.tenant_id == tenant_id)
        .order_by(CompliancePackAssessment.started_at.desc())
    )
    assessments = list(result.scalars().all())

    # Latest assessment per pack_id / pack_name
    seen: dict[str, CompliancePackAssessment] = {}
    for a in assessments:
        key = str(a.pack_id or a.pack_name)
        if key not in seen:
            seen[key] = a

    summary = []
    for a in seen.values():
        findings = a.findings or []
        score = a.overall_score if a.status == "completed" else calculate_score_from_findings(findings)
        total = len(findings)
        compliant = sum(1 for f in findings if f.get("status") == "compliant")
        non_compliant = sum(1 for f in findings if f.get("status") == "non_compliant")
        not_evaluated = sum(1 for f in findings if f.get("status") == "not_evaluated")
        summary.append({
            "assessment_id": str(a.id),
            "pack_id": str(a.pack_id) if a.pack_id else None,
            "pack_name": a.pack_name,
            "status": a.status,
            "score": int(score or 0),
            "total_controls": total,
            "compliant_count": compliant,
            "non_compliant_count": non_compliant,
            "not_evaluated_count": not_evaluated,
            "started_at": a.started_at.isoformat() if a.started_at else None,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
        })
    return summary


# ── Compliance report ─────────────────────────────────────────────────────────

async def generate_compliance_report(
    db: AsyncSession, tenant_id: uuid.UUID, assessment_id: uuid.UUID
) -> dict:
    """Generate structured compliance report from an existing assessment.

    Returns: score, breakdown_by_category, gaps (non_compliant critical/high),
    recommendations.
    """
    result = await db.execute(
        select(CompliancePackAssessment).where(
            CompliancePackAssessment.id == assessment_id,
            CompliancePackAssessment.tenant_id == tenant_id,
        )
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise ValueError("Assessment não encontrado")

    findings = assessment.findings or []
    score = calculate_score_from_findings(findings)

    # Breakdown by category
    categories: dict[str, dict] = {}
    for f in findings:
        cat = f.get("category") or "Geral"
        if cat not in categories:
            categories[cat] = {"compliant": 0, "non_compliant": 0, "partial": 0, "not_evaluated": 0, "not_applicable": 0, "total": 0}
        categories[cat]["total"] += 1
        status = f.get("status", "not_evaluated")
        if status in NON_APPLICABLE_STATUSES:
            categories[cat]["not_applicable"] += 1
        elif status == "compliant":
            categories[cat]["compliant"] += 1
        elif status == "non_compliant":
            categories[cat]["non_compliant"] += 1
        elif status == "partial":
            categories[cat]["partial"] += 1
        else:
            categories[cat]["not_evaluated"] += 1

    # Gaps: non_compliant controls with critical or high severity
    gaps = [
        {
            "control_id": f.get("control_id"),
            "title": f.get("title"),
            "category": f.get("category"),
            "severity": f.get("severity"),
            "evidence": f.get("evidence", ""),
        }
        for f in findings
        if f.get("status") == "non_compliant"
        and f.get("severity") in ("critical", "high")
    ]
    gaps.sort(key=lambda x: (0 if x["severity"] == "critical" else 1, x.get("control_id") or ""))

    # Recommendations from gaps
    recommendations = [
        {
            "priority": i + 1,
            "control_id": g["control_id"],
            "title": f"Remediar: {g['title']}",
            "severity": g["severity"],
            "category": g["category"],
        }
        for i, g in enumerate(gaps[:10])
    ]

    return {
        "assessment_id": str(assessment.id),
        "pack_name": assessment.pack_name,
        "status": assessment.status,
        "score": score,
        "total_controls": len(findings),
        "compliant_count": sum(1 for f in findings if f.get("status") == "compliant"),
        "non_compliant_count": sum(1 for f in findings if f.get("status") == "non_compliant"),
        "not_evaluated_count": sum(1 for f in findings if f.get("status") == "not_evaluated"),
        "breakdown_by_category": categories,
        "gaps": gaps,
        "recommendations": recommendations,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── SLA report ────────────────────────────────────────────────────────────────

async def get_sla_report(db: AsyncSession, tenant_id: uuid.UUID, days: int = 30) -> dict:
    """Generate SLA metrics report for the tenant.

    Calculates: total operations, uptime estimate, MTTR, comparison with SLA targets.
    """
    from datetime import timedelta

    # Get SLA config
    sla_result = await db.execute(
        select(SlaConfig)
        .where(SlaConfig.tenant_id == tenant_id)
        .order_by(SlaConfig.tier_name)
    )
    sla_configs = list(sla_result.scalars().all())

    # Try to get real operation data
    period_start = datetime.now(timezone.utc) - timedelta(days=days)
    total_ops = 0
    completed_ops = 0
    avg_duration_minutes = 0.0

    try:
        from app.models.operation import Operation
        ops_result = await db.execute(
            select(Operation).where(
                Operation.tenant_id == tenant_id,
                Operation.created_at >= period_start,
            )
        )
        ops = list(ops_result.scalars().all())
        total_ops = len(ops)
        completed_ops = sum(1 for o in ops if getattr(o, "status", "") == "completed")
        # Estimate MTTR from completed operations if duration available
        durations = []
        for o in ops:
            created = getattr(o, "created_at", None)
            updated = getattr(o, "updated_at", None)
            if created and updated and updated > created:
                diff = (updated - created).total_seconds() / 60
                if diff < 1440:  # ignore >24h outliers
                    durations.append(diff)
        if durations:
            avg_duration_minutes = round(sum(durations) / len(durations), 1)
    except Exception:
        pass  # Operation model may differ — return estimates

    # Estimate uptime from operations
    # Simple heuristic: if no operations failed catastrophically, uptime ~99.9%
    uptime_pct = 99.9 if total_ops == 0 else round(
        (completed_ops / total_ops) * 100 if total_ops > 0 else 99.9, 2
    )

    # Compare with SLA targets
    critical_config = next((s for s in sla_configs if s.tier_name == "critical"), None)
    high_config = next((s for s in sla_configs if s.tier_name == "high"), None)

    uptime_target = 99.9  # default
    mttr_target_minutes = (critical_config.resolution_hours * 60) if critical_config else 120

    sla_met = uptime_pct >= uptime_target and (avg_duration_minutes <= mttr_target_minutes or avg_duration_minutes == 0)

    return {
        "period_days": days,
        "period_start": period_start.isoformat(),
        "period_end": datetime.now(timezone.utc).isoformat(),
        "total_operations": total_ops,
        "completed_operations": completed_ops,
        "uptime_pct": uptime_pct,
        "uptime_target_pct": uptime_target,
        "mttr_minutes": avg_duration_minutes,
        "mttr_target_minutes": mttr_target_minutes,
        "sla_met": sla_met,
        "sla_configs": [
            {
                "tier": s.tier_name,
                "response_minutes": s.response_minutes,
                "resolution_hours": s.resolution_hours,
                "escalation_hours": s.escalation_hours,
                "is_active": s.is_active,
            }
            for s in sla_configs
        ],
    }
