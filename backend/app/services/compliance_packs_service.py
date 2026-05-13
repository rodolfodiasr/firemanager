"""Service — F30 Compliance Enterprise: packs, assessments, BC/DR, SLA."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

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

# ── Built-in compliance packs ─────────────────────────────────────────────────

_BUILTIN_PACKS: list[dict] = [
    {
        "name": "CIS Controls v8 — Level 1",
        "framework": "cis_l1",
        "version": "v8",
        "description": "Controles CIS nível 1 — implementação básica de segurança.",
        "controls": [
            {"control_id": "CIS-1.1", "title": "Inventário de Ativos de Hardware", "category": "Inventário", "severity": "high", "verification_type": "automated", "evidence_hint": "Export do inventário Zabbix/GLPI"},
            {"control_id": "CIS-1.2", "title": "Inventário de Ativos de Software", "category": "Inventário", "severity": "high", "verification_type": "automated"},
            {"control_id": "CIS-2.1", "title": "Configurações Seguras para Hardware e Software", "category": "Configuração", "severity": "critical", "verification_type": "automated"},
            {"control_id": "CIS-3.1", "title": "Proteção de Dados — Identificação e Classificação", "category": "Dados", "severity": "high", "verification_type": "manual"},
            {"control_id": "CIS-4.1", "title": "Gestão Segura de Credenciais", "category": "Acesso", "severity": "critical", "verification_type": "manual", "evidence_hint": "Política de senhas, MFA habilitado"},
            {"control_id": "CIS-5.1", "title": "Gerenciamento de Contas", "category": "Acesso", "severity": "high", "verification_type": "automated"},
            {"control_id": "CIS-6.1", "title": "Gestão de Controle de Acesso", "category": "Acesso", "severity": "critical", "verification_type": "manual"},
            {"control_id": "CIS-7.1", "title": "Gestão Contínua de Vulnerabilidades", "category": "Vulnerabilidades", "severity": "high", "verification_type": "automated", "evidence_hint": "Relatório de scan OpenVAS/Nmap"},
            {"control_id": "CIS-8.1", "title": "Gerenciamento de Log de Auditoria", "category": "Auditoria", "severity": "high", "verification_type": "automated"},
            {"control_id": "CIS-9.1", "title": "Proteção de Email e Navegador Web", "category": "Proteção", "severity": "medium", "verification_type": "manual"},
            {"control_id": "CIS-10.1", "title": "Defesas contra Malware", "category": "Proteção", "severity": "critical", "verification_type": "manual"},
            {"control_id": "CIS-12.1", "title": "Gerenciamento da Infraestrutura de Rede", "category": "Rede", "severity": "high", "verification_type": "automated"},
            {"control_id": "CIS-13.1", "title": "Monitoramento e Defesa de Rede", "category": "Rede", "severity": "high", "verification_type": "automated"},
        ],
    },
    {
        "name": "PCI-DSS v4.0",
        "framework": "pci_dss",
        "version": "v4.0",
        "description": "Payment Card Industry Data Security Standard v4.0.",
        "controls": [
            {"control_id": "PCI-1.2", "title": "Controles de Segurança de Rede", "category": "Rede", "severity": "critical", "verification_type": "automated", "evidence_hint": "Regras de firewall documentadas"},
            {"control_id": "PCI-1.3", "title": "Acesso de Rede Restrito ao Ambiente de Dados do Portador de Cartão", "category": "Rede", "severity": "critical", "verification_type": "automated"},
            {"control_id": "PCI-2.2", "title": "Configurações Seguras para Todos os Componentes do Sistema", "category": "Configuração", "severity": "critical", "verification_type": "automated"},
            {"control_id": "PCI-3.4", "title": "Proteção de Dados Armazenados", "category": "Dados", "severity": "critical", "verification_type": "manual"},
            {"control_id": "PCI-4.2", "title": "Transmissão Segura de Dados do Portador de Cartão", "category": "Dados", "severity": "critical", "verification_type": "manual", "evidence_hint": "TLS 1.2+ em todos os canais"},
            {"control_id": "PCI-6.3", "title": "Segurança de Aplicações Desenvolvidas e Mantidas", "category": "Aplicação", "severity": "high", "verification_type": "manual"},
            {"control_id": "PCI-7.2", "title": "Acesso a Componentes e Dados do Sistema Restrito", "category": "Acesso", "severity": "critical", "verification_type": "manual"},
            {"control_id": "PCI-8.2", "title": "Identificação e Autenticação de Usuário", "category": "Acesso", "severity": "critical", "verification_type": "automated", "evidence_hint": "MFA habilitado para todos os administradores"},
            {"control_id": "PCI-10.2", "title": "Logs de Auditoria para Detectar Anomalias e Atividades Suspeitas", "category": "Auditoria", "severity": "high", "verification_type": "automated"},
            {"control_id": "PCI-10.3", "title": "Logs de Auditoria Protegidos contra Destruição e Modificações Não Autorizadas", "category": "Auditoria", "severity": "high", "verification_type": "automated"},
            {"control_id": "PCI-11.3", "title": "Ameaças Externas e Internas Identificadas e Gerenciadas", "category": "Vulnerabilidades", "severity": "high", "verification_type": "manual"},
            {"control_id": "PCI-12.3", "title": "Riscos Identificados, Avaliados e Gerenciados", "category": "Governança", "severity": "high", "verification_type": "manual"},
        ],
    },
    {
        "name": "LGPD — Lei Geral de Proteção de Dados",
        "framework": "lgpd",
        "version": "Lei 13.709/2018",
        "description": "Controles de conformidade com a LGPD — privacidade e proteção de dados pessoais.",
        "controls": [
            {"control_id": "LGPD-6", "title": "Princípio da Finalidade — Dados coletados com propósito específico", "category": "Princípios", "severity": "critical", "verification_type": "manual"},
            {"control_id": "LGPD-7", "title": "Base Legal para Tratamento de Dados", "category": "Princípios", "severity": "critical", "verification_type": "manual", "evidence_hint": "Mapeamento de bases legais documentado"},
            {"control_id": "LGPD-9", "title": "Transparência — Titular informado sobre tratamento", "category": "Direitos", "severity": "high", "verification_type": "manual"},
            {"control_id": "LGPD-18", "title": "Direitos do Titular — Confirmação, acesso, correção, portabilidade, eliminação", "category": "Direitos", "severity": "critical", "verification_type": "manual"},
            {"control_id": "LGPD-46", "title": "Medidas de Segurança Técnicas e Administrativas", "category": "Segurança", "severity": "critical", "verification_type": "automated", "evidence_hint": "Criptografia, controle de acesso, logs de auditoria"},
            {"control_id": "LGPD-48", "title": "Notificação de Incidentes de Segurança à ANPD", "category": "Incidentes", "severity": "critical", "verification_type": "manual"},
            {"control_id": "LGPD-50", "title": "Política de Proteção de Dados documentada", "category": "Governança", "severity": "high", "verification_type": "manual"},
            {"control_id": "LGPD-DPO", "title": "Encarregado de Dados (DPO) designado", "category": "Governança", "severity": "medium", "verification_type": "manual"},
            {"control_id": "LGPD-RIPD", "title": "Relatório de Impacto à Proteção de Dados (RIPD)", "category": "Governança", "severity": "high", "verification_type": "manual"},
        ],
    },
    {
        "name": "BACEN — CMN 4.893 / Resolução 4.658",
        "framework": "bacen",
        "version": "CMN 4.893",
        "description": "Política de segurança cibernética para instituições financeiras (BACEN).",
        "controls": [
            {"control_id": "BACEN-4893-I", "title": "Política de Segurança Cibernética documentada e aprovada pela diretoria", "category": "Governança", "severity": "critical", "verification_type": "manual"},
            {"control_id": "BACEN-4893-II", "title": "Objetivos de segurança cibernética definidos com indicadores", "category": "Governança", "severity": "high", "verification_type": "manual"},
            {"control_id": "BACEN-4893-III", "title": "Procedimentos e controles para reduzir vulnerabilidades", "category": "Controles", "severity": "critical", "verification_type": "automated"},
            {"control_id": "BACEN-4893-IV", "title": "Registro, análise e resposta a incidentes", "category": "Incidentes", "severity": "critical", "verification_type": "automated", "evidence_hint": "Playbooks SOAR configurados, histórico de incidentes"},
            {"control_id": "BACEN-4893-V", "title": "Programa de capacitação e treinamento em segurança cibernética", "category": "Pessoas", "severity": "medium", "verification_type": "manual"},
            {"control_id": "BACEN-4893-VI", "title": "Classificação de dados e gestão de risco", "category": "Dados", "severity": "high", "verification_type": "manual"},
            {"control_id": "BACEN-4893-VII", "title": "Plano de continuidade de negócios (BC/DR)", "category": "Continuidade", "severity": "critical", "verification_type": "manual", "evidence_hint": "Plano BC/DR com RTO/RPO documentados e testados"},
            {"control_id": "BACEN-4893-VIII", "title": "Relatório anual de segurança cibernética ao Conselho", "category": "Governança", "severity": "high", "verification_type": "manual"},
            {"control_id": "BACEN-4658-I", "title": "Gestão de risco operacional — políticas e procedimentos", "category": "Risco", "severity": "high", "verification_type": "manual"},
        ],
    },
]

_DEFAULT_SLA_TIERS = [
    {"tier_name": "critical", "response_minutes": 15, "resolution_hours": 2, "escalation_hours": 1},
    {"tier_name": "high",     "response_minutes": 60, "resolution_hours": 8, "escalation_hours": 4},
    {"tier_name": "medium",   "response_minutes": 240, "resolution_hours": 24, "escalation_hours": 12},
    {"tier_name": "low",      "response_minutes": 480, "resolution_hours": 72, "escalation_hours": 48},
]


# ── Pack management ───────────────────────────────────────────────────────────

async def list_packs(db: AsyncSession) -> list[CompliancePack]:
    result = await db.execute(
        select(CompliancePack)
        .where(CompliancePack.is_active == True)
        .options(selectinload(CompliancePack.controls))
        .order_by(CompliancePack.name)
    )
    return list(result.scalars().all())


async def get_pack(db: AsyncSession, pack_id: uuid.UUID) -> CompliancePack | None:
    result = await db.execute(
        select(CompliancePack)
        .where(CompliancePack.id == pack_id)
        .options(selectinload(CompliancePack.controls))
    )
    return result.scalar_one_or_none()


async def seed_builtin_packs(db: AsyncSession) -> int:
    existing = await db.execute(select(CompliancePack.framework))
    existing_frameworks = {row[0] for row in existing.all()}

    created = 0
    for pack_data in _BUILTIN_PACKS:
        if pack_data["framework"] in existing_frameworks:
            continue
        pack = CompliancePack(
            name=pack_data["name"],
            framework=pack_data["framework"],
            version=pack_data.get("version"),
            description=pack_data.get("description"),
            is_builtin=True,
            is_active=True,
        )
        db.add(pack)
        await db.flush()
        for i, ctrl in enumerate(pack_data.get("controls", [])):
            db.add(CompliancePackControl(
                pack_id=pack.id,
                control_id=ctrl["control_id"],
                title=ctrl["title"],
                description=ctrl.get("description"),
                category=ctrl.get("category"),
                severity=ctrl.get("severity", "medium"),
                verification_type=ctrl.get("verification_type", "manual"),
                evidence_hint=ctrl.get("evidence_hint"),
                sort_order=i,
            ))
        created += 1
    await db.commit()
    return created


# ── Assessments ───────────────────────────────────────────────────────────────

async def list_assessments(
    db: AsyncSession, tenant_id: uuid.UUID, limit: int = 50
) -> list[CompliancePackAssessment]:
    result = await db.execute(
        select(CompliancePackAssessment)
        .where(CompliancePackAssessment.tenant_id == tenant_id)
        .order_by(CompliancePackAssessment.started_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_assessment(
    db: AsyncSession, tenant_id: uuid.UUID, assessment_id: uuid.UUID
) -> CompliancePackAssessment | None:
    result = await db.execute(
        select(CompliancePackAssessment).where(
            CompliancePackAssessment.id == assessment_id,
            CompliancePackAssessment.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_assessment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    pack_id: uuid.UUID,
    name: str,
    user_id: uuid.UUID | None = None,
) -> CompliancePackAssessment:
    pack = await get_pack(db, pack_id)
    if not pack:
        raise ValueError("Pack não encontrado")

    assessment = CompliancePackAssessment(
        tenant_id=tenant_id,
        pack_id=pack_id,
        pack_name=pack.name,
        name=name,
        status="in_progress",
        total_controls=len(pack.controls),
        findings=[
            {
                "control_id": ctrl.control_id,
                "title": ctrl.title,
                "category": ctrl.category,
                "severity": ctrl.severity,
                "status": "not_evaluated",
                "evidence": "",
                "notes": "",
            }
            for ctrl in pack.controls
        ],
        created_by=user_id,
    )
    db.add(assessment)
    await db.flush()
    await db.refresh(assessment)
    await db.commit()
    return assessment


async def update_assessment_finding(
    db: AsyncSession,
    assessment: CompliancePackAssessment,
    control_id: str,
    status: str,
    evidence: str,
    notes: str,
) -> CompliancePackAssessment:
    findings = list(assessment.findings or [])
    for f in findings:
        if f.get("control_id") == control_id:
            f["status"] = status
            f["evidence"] = evidence
            f["notes"] = notes
            break
    assessment.findings = findings
    await db.flush()
    await db.refresh(assessment)
    return assessment


async def complete_assessment(
    db: AsyncSession, assessment: CompliancePackAssessment
) -> CompliancePackAssessment:
    findings = assessment.findings or []
    compliant = sum(1 for f in findings if f.get("status") == "compliant")
    partial = sum(1 for f in findings if f.get("status") == "partial")
    non_compliant = sum(1 for f in findings if f.get("status") == "non_compliant")
    total = len(findings)

    score = (compliant + partial * 0.5) / total * 100 if total > 0 else 0.0

    assessment.status = "completed"
    assessment.overall_score = round(score, 1)
    assessment.compliant_count = compliant
    assessment.partial_count = partial
    assessment.non_compliant_count = non_compliant
    assessment.completed_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(assessment)
    await db.commit()
    return assessment


# ── BC/DR Plans ───────────────────────────────────────────────────────────────

async def list_bcdr_plans(db: AsyncSession, tenant_id: uuid.UUID) -> list[BcdrPlan]:
    result = await db.execute(
        select(BcdrPlan)
        .where(BcdrPlan.tenant_id == tenant_id)
        .order_by(BcdrPlan.created_at.desc())
    )
    return list(result.scalars().all())


async def get_bcdr_plan(
    db: AsyncSession, tenant_id: uuid.UUID, plan_id: uuid.UUID
) -> BcdrPlan | None:
    result = await db.execute(
        select(BcdrPlan).where(BcdrPlan.id == plan_id, BcdrPlan.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def create_bcdr_plan(
    db: AsyncSession, tenant_id: uuid.UUID, data: dict
) -> BcdrPlan:
    plan = BcdrPlan(tenant_id=tenant_id, **data)
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    await db.commit()
    return plan


async def update_bcdr_plan(
    db: AsyncSession, plan: BcdrPlan, data: dict
) -> BcdrPlan:
    for k, v in data.items():
        setattr(plan, k, v)
    await db.flush()
    await db.refresh(plan)
    await db.commit()
    return plan


async def record_bcdr_test(
    db: AsyncSession, plan: BcdrPlan, result: str, notes: str
) -> BcdrPlan:
    plan.last_test_at = datetime.now(timezone.utc)
    plan.last_test_result = result
    plan.last_test_notes = notes
    await db.flush()
    await db.refresh(plan)
    await db.commit()
    return plan


# ── SLA Configs ───────────────────────────────────────────────────────────────

async def get_sla_configs(db: AsyncSession, tenant_id: uuid.UUID) -> list[SlaConfig]:
    result = await db.execute(
        select(SlaConfig)
        .where(SlaConfig.tenant_id == tenant_id)
        .order_by(SlaConfig.tier_name)
    )
    return list(result.scalars().all())


async def seed_sla_defaults(db: AsyncSession, tenant_id: uuid.UUID) -> list[SlaConfig]:
    existing = await db.execute(
        select(SlaConfig.tier_name).where(SlaConfig.tenant_id == tenant_id)
    )
    existing_tiers = {row[0] for row in existing.all()}
    created = []
    for tier in _DEFAULT_SLA_TIERS:
        if tier["tier_name"] in existing_tiers:
            continue
        obj = SlaConfig(tenant_id=tenant_id, **tier)
        db.add(obj)
        created.append(obj)
    if created:
        await db.flush()
        for obj in created:
            await db.refresh(obj)
        await db.commit()
    return created


async def upsert_sla_config(
    db: AsyncSession, tenant_id: uuid.UUID, tier_name: str, data: dict
) -> SlaConfig:
    result = await db.execute(
        select(SlaConfig).where(SlaConfig.tenant_id == tenant_id, SlaConfig.tier_name == tier_name)
    )
    obj = result.scalar_one_or_none()
    if obj:
        for k, v in data.items():
            setattr(obj, k, v)
    else:
        obj = SlaConfig(tenant_id=tenant_id, tier_name=tier_name, **data)
        db.add(obj)
    await db.flush()
    await db.refresh(obj)
    await db.commit()
    return obj
