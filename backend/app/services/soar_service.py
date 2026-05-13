"""F35 — SOAR Service: avaliação de playbooks, execução de actions e templates AD."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.playbook import PlaybookExecution, PlaybookRule

# ── Templates de playbook pré-prontos para AD ─────────────────────────────────

AD_PLAYBOOK_TEMPLATES: list[dict] = [
    {
        "template_name": "offboarding_imediato",
        "name": "Offboarding Imediato (AD)",
        "description": "Desabilita conta, revoga grupos críticos e notifica RH ao detectar demissão.",
        "trigger_type": "identity_anomaly",
        "trigger_condition": {"event": "user_offboarded"},
        "actions": [
            {"type": "ad_disable_user", "params": {"reason": "Offboarding automático"}},
            {"type": "notify_slack", "params": {"message": "Conta {upn} desabilitada por offboarding"}},
            {"type": "create_ticket_jira", "params": {"summary": "Offboarding: {upn}", "priority": "Medium"}},
        ],
        "cooldown_minutes": 0,
    },
    {
        "template_name": "conta_comprometida",
        "name": "Conta Comprometida — Resposta Automática",
        "description": "Detecta login suspeito via SIEM e desabilita conta preventivamente.",
        "trigger_type": "siem_alert",
        "trigger_condition": {"severity": "critical", "rule_contains": "brute_force"},
        "actions": [
            {"type": "ad_disable_user", "params": {"reason": "Conta comprometida — bloqueio automático"}},
            {"type": "revoke_jit_access", "params": {}},
            {"type": "notify_slack", "params": {"message": "ALERTA: Conta {upn} bloqueada por suspeita de comprometimento"}},
            {"type": "create_ticket_jira", "params": {"summary": "Incidente: Conta comprometida {upn}", "priority": "High"}},
        ],
        "cooldown_minutes": 60,
    },
    {
        "template_name": "jit_abuso",
        "name": "Abuso de JIT Access",
        "description": "Revoga acesso JIT se volume de acesso anômalo for detectado.",
        "trigger_type": "jit_abuse",
        "trigger_condition": {"access_count_threshold": 50, "window_minutes": 10},
        "actions": [
            {"type": "revoke_jit_access", "params": {}},
            {"type": "notify_slack", "params": {"message": "JIT abuso detectado para {upn}"}},
            {"type": "escalate_to_n2", "params": {}},
        ],
        "cooldown_minutes": 15,
    },
    {
        "template_name": "violacao_sod",
        "name": "Violação de SoD Detectada",
        "description": "Notifica manager e cria task de revisão ao detectar conflito de funções.",
        "trigger_type": "sod_violation",
        "trigger_condition": {"severity": "critical"},
        "actions": [
            {"type": "notify_slack", "params": {"message": "SoD CRÍTICO detectado para {user_display_name}: {rule_name}"}},
            {"type": "create_ticket_jira", "params": {"summary": "Violação SoD: {rule_name} — {user_display_name}", "priority": "High"}},
            {"type": "notify_email", "params": {"to_manager": True}},
        ],
        "cooldown_minutes": 1440,  # 24h
    },
    {
        "template_name": "device_unreachable_ad",
        "name": "Domain Controller Inacessível",
        "description": "Alerta imediato se um DC ficar fora do ar.",
        "trigger_type": "device_unreachable",
        "trigger_condition": {"device_type": "domain_controller"},
        "actions": [
            {"type": "run_snapshot", "params": {}},
            {"type": "notify_slack", "params": {"message": "DC {device_name} inacessível!"}},
            {"type": "escalate_to_n2", "params": {}},
        ],
        "cooldown_minutes": 5,
    },
]


async def seed_ad_templates(db: AsyncSession, tenant_id: UUID, created_by: UUID) -> int:
    """Instala templates de playbook AD para um tenant (idempotente)."""
    existing_result = await db.execute(
        select(PlaybookRule).where(
            PlaybookRule.tenant_id == tenant_id,
            PlaybookRule.is_template.is_(True),
        ).limit(1)
    )
    if existing_result.scalar_one_or_none():
        return 0   # já tem templates

    count = 0
    for t in AD_PLAYBOOK_TEMPLATES:
        rule = PlaybookRule(
            tenant_id=tenant_id,
            name=t["name"],
            description=t.get("description"),
            trigger_type=t["trigger_type"],
            trigger_condition=t["trigger_condition"],
            actions=t["actions"],
            cooldown_minutes=t.get("cooldown_minutes", 30),
            enabled=False,  # templates começam desabilitados
            is_template=True,
            template_name=t["template_name"],
            created_by=created_by,
        )
        db.add(rule)
        count += 1

    await db.flush()
    await db.commit()
    return count


# ── SOAR evaluator ─────────────────────────────────────────────────────────────

async def evaluate_trigger(
    db: AsyncSession,
    tenant_id: UUID,
    trigger_type: str,
    trigger_context: dict[str, Any],
) -> list[dict]:
    """Avalia todos os playbooks ativos de um tenant para um trigger específico.
    Retorna lista de execuções iniciadas.
    """
    rules_result = await db.execute(
        select(PlaybookRule).where(
            PlaybookRule.tenant_id == tenant_id,
            PlaybookRule.trigger_type == trigger_type,
            PlaybookRule.enabled.is_(True),
        )
    )
    rules = rules_result.scalars().all()
    started: list[dict] = []

    for rule in rules:
        if not _condition_matches(rule.trigger_condition, trigger_context):
            continue

        if await _in_cooldown(db, rule):
            continue

        exec_obj = PlaybookExecution(
            tenant_id=tenant_id,
            rule_id=rule.id,
            trigger_context=trigger_context,
            actions_taken=[],
            status="running",
        )
        db.add(exec_obj)
        await db.flush()
        await db.refresh(exec_obj)

        # Executar actions em background (Celery)
        from app.workers.playbook_evaluator import execute_playbook_actions
        execute_playbook_actions.delay(str(exec_obj.id), json.dumps(rule.actions))

        started.append({"execution_id": str(exec_obj.id), "rule": rule.name})

    if started:
        await db.commit()

    return started


def _condition_matches(condition: dict, context: dict) -> bool:
    """Verificação simples de condição — extensível."""
    if not condition:
        return True
    for key, expected in condition.items():
        actual = context.get(key)
        if actual is None:
            return False
        if isinstance(expected, str) and "contains" in key:
            if expected.lower() not in str(actual).lower():
                return False
        elif str(actual).lower() != str(expected).lower():
            return False
    return True


async def _in_cooldown(db: AsyncSession, rule: PlaybookRule) -> bool:
    if rule.cooldown_minutes <= 0:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=rule.cooldown_minutes)
    result = await db.execute(
        select(PlaybookExecution).where(
            PlaybookExecution.rule_id == rule.id,
            PlaybookExecution.triggered_at >= cutoff,
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def get_mttr_stats(db: AsyncSession, tenant_id: UUID) -> dict:
    """Calcula MTTR (Mean Time to Resolution) por playbook."""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT
                r.name,
                COUNT(*) as executions,
                AVG(EXTRACT(EPOCH FROM (e.resolved_at - e.triggered_at)) / 60) as avg_mttr_minutes
            FROM playbook_executions e
            JOIN playbook_rules r ON r.id = e.rule_id
            WHERE e.tenant_id = :tid AND e.resolved_at IS NOT NULL
            GROUP BY r.name
            ORDER BY avg_mttr_minutes
        """),
        {"tid": str(tenant_id)},
    )
    rows = result.all()
    return {
        "playbooks": [
            {"name": r[0], "executions": r[1], "avg_mttr_minutes": round(r[2] or 0, 1)}
            for r in rows
        ]
    }
