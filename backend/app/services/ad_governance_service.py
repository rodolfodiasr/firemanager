"""AD Tool Kit — ferramentas determinísticas para governança de AD/M365.

O LLM (IdentityAgent) apenas seleciona a tool e os parâmetros.
A execução é determinística — sem alucinação possível na operação em si.
Toda escrita passa por:  preview → guardrail_check → audit_log → execução.
"""
from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# ── Tool Kit Read (sem guardrail) ──────────────────────────────────────────────

async def ad_list_users(
    ad_config: dict,
    department: str | None = None,
    enabled_only: bool = False,
) -> list[dict]:
    from app.services import local_ad_service as ldap
    users = await ldap.list_users(ad_config)
    if department:
        users = [u for u in users if (u.get("department") or "").lower() == department.lower()]
    if enabled_only:
        users = [u for u in users if u.get("is_enabled")]
    return users


async def ad_list_inactive_users(ad_config: dict, days: int = 60) -> list[dict]:
    from app.services import local_ad_service as ldap
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    users = await ldap.list_users(ad_config)
    inactive = []
    for u in users:
        ls = u.get("last_logon_str")
        if not ls:
            inactive.append(u)
            continue
        try:
            last = datetime.fromisoformat(ls)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last < cutoff:
                inactive.append(u)
        except ValueError:
            inactive.append(u)
    return inactive


async def ad_get_user(ad_config: dict, username_or_upn: str) -> dict | None:
    from app.services import local_ad_service as ldap
    return await ldap.find_user(ad_config, username_or_upn)


async def ad_get_group_members(ad_config: dict, group_name: str) -> list[dict]:
    from app.services import local_ad_service as ldap
    return await ldap.get_group_members(ad_config, group_name)


async def ad_list_groups(ad_config: dict) -> list[dict]:
    from app.services import local_ad_service as ldap
    return await ldap.list_groups(ad_config)


async def ad_compliance_report(ad_config: dict, report_type: str) -> dict[str, Any]:
    users = await ad_list_users(ad_config)
    if report_type == "inativos":
        result = await ad_list_inactive_users(ad_config, days=60)
        return {"report_type": report_type, "total": len(result), "items": result[:100]}
    if report_type == "desabilitados":
        result = [u for u in users if not u.get("is_enabled")]
        return {"report_type": report_type, "total": len(result), "items": result[:100]}
    if report_type == "sem_logon":
        result = [u for u in users if not u.get("last_logon_str")]
        return {"report_type": report_type, "total": len(result), "items": result[:100]}
    return {"report_type": report_type, "total": len(users), "items": users[:100]}


# ── Tool Kit Write (requer guardrail + audit) ──────────────────────────────────

async def ad_disable_user(
    ad_config: dict,
    username_or_upn: str,
    reason: str,
    db: AsyncSession,
    tenant_id: UUID,
    operator_id: UUID,
) -> dict:
    from app.services import local_ad_service as ldap
    from app.services.audit_log_service import write_audit

    user = await ldap.find_user(ad_config, username_or_upn)
    if not user:
        return {"success": False, "error": f"Usuário '{username_or_upn}' não encontrado no AD"}

    dn = user["dn"]
    await ldap.disable_user(ad_config, dn)

    await write_audit(
        db=db,
        tenant_id=tenant_id,
        user_id=operator_id,
        action="ad_disable_user",
        resource_type="ad_user",
        resource_id=username_or_upn,
        details={"dn": dn, "reason": reason},
    )

    return {"success": True, "user": username_or_upn, "dn": dn, "action": "disabled"}


async def ad_enable_user(
    ad_config: dict,
    username_or_upn: str,
    reason: str,
    db: AsyncSession,
    tenant_id: UUID,
    operator_id: UUID,
) -> dict:
    from app.services import local_ad_service as ldap
    from app.services.audit_log_service import write_audit

    user = await ldap.find_user(ad_config, username_or_upn)
    if not user:
        return {"success": False, "error": f"Usuário '{username_or_upn}' não encontrado no AD"}

    dn = user["dn"]
    await ldap.enable_user(ad_config, dn)

    await write_audit(
        db=db,
        tenant_id=tenant_id,
        user_id=operator_id,
        action="ad_enable_user",
        resource_type="ad_user",
        resource_id=username_or_upn,
        details={"dn": dn, "reason": reason},
    )

    return {"success": True, "user": username_or_upn, "dn": dn, "action": "enabled"}


async def ad_reset_password(
    ad_config: dict,
    username_or_upn: str,
    db: AsyncSession,
    tenant_id: UUID,
    operator_id: UUID,
) -> dict:
    from app.services import local_ad_service as ldap
    from app.services.audit_log_service import write_audit

    user = await ldap.find_user(ad_config, username_or_upn)
    if not user:
        return {"success": False, "error": f"Usuário '{username_or_upn}' não encontrado no AD"}

    dn = user["dn"]
    new_password = _generate_temp_password()
    await ldap.reset_password(ad_config, dn, new_password)

    await write_audit(
        db=db,
        tenant_id=tenant_id,
        user_id=operator_id,
        action="ad_reset_password",
        resource_type="ad_user",
        resource_id=username_or_upn,
        details={"dn": dn, "must_change_at_next_logon": True},
    )

    return {
        "success": True,
        "user": username_or_upn,
        "temp_password": new_password,
        "must_change": True,
    }


async def ad_add_to_group(
    ad_config: dict,
    username_or_upn: str,
    group_name: str,
    reason: str,
    db: AsyncSession,
    tenant_id: UUID,
    operator_id: UUID,
) -> dict:
    from app.services import local_ad_service as ldap
    from app.services.audit_log_service import write_audit

    user = await ldap.find_user(ad_config, username_or_upn)
    if not user:
        return {"success": False, "error": f"Usuário '{username_or_upn}' não encontrado"}

    await ldap.add_user_to_groups(ad_config, user["dn"], [group_name])

    await write_audit(
        db=db,
        tenant_id=tenant_id,
        user_id=operator_id,
        action="ad_add_to_group",
        resource_type="ad_group",
        resource_id=group_name,
        details={"user": username_or_upn, "group": group_name, "reason": reason},
    )

    return {"success": True, "user": username_or_upn, "group": group_name, "action": "added"}


async def ad_remove_from_group(
    ad_config: dict,
    username_or_upn: str,
    group_name: str,
    reason: str,
    db: AsyncSession,
    tenant_id: UUID,
    operator_id: UUID,
) -> dict:
    from app.services import local_ad_service as ldap
    from app.services.audit_log_service import write_audit

    user = await ldap.find_user(ad_config, username_or_upn)
    if not user:
        return {"success": False, "error": f"Usuário '{username_or_upn}' não encontrado"}

    await ldap.remove_user_from_group(ad_config, user["dn"], group_name)

    await write_audit(
        db=db,
        tenant_id=tenant_id,
        user_id=operator_id,
        action="ad_remove_from_group",
        resource_type="ad_group",
        resource_id=group_name,
        details={"user": username_or_upn, "group": group_name, "reason": reason},
    )

    return {"success": True, "user": username_or_upn, "group": group_name, "action": "removed"}


async def ad_batch_disable_users(
    ad_config: dict,
    upn_list: list[str],
    reason: str,
    db: AsyncSession,
    tenant_id: UUID,
    operator_id: UUID,
) -> dict:
    results = []
    for upn in upn_list:
        r = await ad_disable_user(ad_config, upn, reason, db, tenant_id, operator_id)
        results.append(r)

    success_count = sum(1 for r in results if r.get("success"))
    return {
        "total": len(upn_list),
        "success": success_count,
        "failed": len(upn_list) - success_count,
        "results": results,
    }


# ── JIT Service ────────────────────────────────────────────────────────────────

async def jit_request_create(
    db: AsyncSession,
    tenant_id: UUID,
    requester_id: UUID,
    target_group_name: str,
    reason: str,
    duration_hours: int,
) -> dict:
    from app.models.identity_governance import JitRequest

    if len(reason.strip()) < 20:
        return {"success": False, "error": "Justificativa deve ter ao menos 20 caracteres"}

    jit = JitRequest(
        tenant_id=tenant_id,
        requester_id=requester_id,
        target_group_name=target_group_name,
        reason=reason,
        duration_hours=duration_hours,
        status="pending",
    )
    db.add(jit)
    await db.flush()
    await db.refresh(jit)
    await db.commit()

    return {"success": True, "jit_id": str(jit.id), "status": "pending"}


async def jit_approve(
    db: AsyncSession,
    jit_id: UUID,
    tenant_id: UUID,
    approver_id: UUID,
    ad_config: dict | None,
    operator_id: UUID,
) -> dict:
    from app.models.identity_governance import JitRequest
    from app.services import local_ad_service as ldap
    from app.services.audit_log_service import write_audit

    result = await db.execute(
        select(JitRequest).where(
            JitRequest.id == jit_id,
            JitRequest.tenant_id == tenant_id,
            JitRequest.status == "pending",
        )
    )
    jit = result.scalar_one_or_none()
    if not jit:
        return {"success": False, "error": "JIT request não encontrado ou já processado"}

    now = datetime.now(timezone.utc)
    jit.approver_id = approver_id
    jit.approved_at = now
    jit.granted_at = now
    jit.expires_at = now + timedelta(hours=jit.duration_hours)
    jit.status = "active"

    # Adicionar ao grupo no AD se config disponível
    if ad_config and jit.target_group_name:
        try:
            # Obter o upn do requester
            from sqlalchemy import select as sa_select
            from app.models.user import User
            user_result = await db.execute(sa_select(User).where(User.id == jit.requester_id))
            user = user_result.scalar_one_or_none()
            if user and user.email:
                await ldap.add_user_to_groups(ad_config, user.email, [jit.target_group_name])
        except Exception:
            pass   # JIT registrado mesmo se AD falhar

    await write_audit(
        db=db,
        tenant_id=tenant_id,
        user_id=approver_id,
        action="jit_approved",
        resource_type="jit_request",
        resource_id=str(jit_id),
        details={
            "group": jit.target_group_name,
            "duration_hours": jit.duration_hours,
            "expires_at": jit.expires_at.isoformat(),
        },
    )

    await db.flush()
    await db.refresh(jit)
    await db.commit()

    return {
        "success": True,
        "jit_id": str(jit.id),
        "status": "active",
        "expires_at": jit.expires_at.isoformat(),
    }


async def jit_expire_check(db: AsyncSession) -> int:
    """Revoga JIT requests expirados. Chamado pelo Celery beat."""
    from app.models.identity_governance import JitRequest

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(JitRequest).where(
            JitRequest.status == "active",
            JitRequest.expires_at <= now,
        )
    )
    expired = result.scalars().all()
    for jit in expired:
        jit.status = "expired"
        jit.revoked_at = now

    if expired:
        await db.commit()

    return len(expired)


# ── SoD Checker ───────────────────────────────────────────────────────────────

async def sod_check_user(
    db: AsyncSession,
    tenant_id: UUID,
    ad_user_id: UUID,
    user_groups: list[str],
) -> list[dict]:
    """Verifica violações de SoD para um usuário específico."""
    from app.models.identity_governance import SodRule, SodViolation

    rules_result = await db.execute(
        select(SodRule).where(
            SodRule.tenant_id == tenant_id,
            SodRule.enabled.is_(True),
        )
    )
    rules = rules_result.scalars().all()
    violations = []

    groups_lower = {g.lower() for g in user_groups}
    for rule in rules:
        a_in = rule.role_a_name.lower() in groups_lower
        b_in = rule.role_b_name.lower() in groups_lower
        if a_in and b_in:
            # Upsert violation
            existing = await db.execute(
                select(SodViolation).where(
                    SodViolation.user_id == ad_user_id,
                    SodViolation.rule_id == rule.id,
                    SodViolation.status == "open",
                )
            )
            if not existing.scalar_one_or_none():
                v = SodViolation(
                    tenant_id=tenant_id,
                    user_id=ad_user_id,
                    rule_id=rule.id,
                    status="open",
                )
                db.add(v)
            violations.append({
                "rule_id": str(rule.id),
                "rule_name": rule.name,
                "severity": rule.severity,
                "risk": rule.risk_description,
            })

    if violations:
        await db.commit()

    return violations


# ── SoD Builtin Library (seed) ─────────────────────────────────────────────────

BUILTIN_SOD_RULES: list[dict] = [
    {
        "name": "Contas a Pagar + Aprovação Financeira",
        "role_a_name": "Contas a Pagar",
        "role_b_name": "Aprovação Financeira",
        "severity": "critical",
        "risk_description": "Usuário pode criar e aprovar próprios pagamentos",
        "remediation_suggestion": "Remover da 'Aprovação Financeira' ou criar conta separada",
    },
    {
        "name": "Domain Admins + Sistema Financeiro",
        "role_a_name": "Domain Admins",
        "role_b_name": "Usuários do ERP",
        "severity": "critical",
        "risk_description": "Admin de infra com acesso a dados financeiros — sem segregação",
        "remediation_suggestion": "Domain Admin deve usar conta separada para sistemas de negócio",
    },
    {
        "name": "TI Help Desk + Domain Admins",
        "role_a_name": "Help Desk",
        "role_b_name": "Domain Admins",
        "severity": "high",
        "risk_description": "Help Desk com poder de alterar qualquer conta do AD",
        "remediation_suggestion": "Remover de Domain Admins — usar delegação específica",
    },
    {
        "name": "Auditoria + Administração de Sistemas",
        "role_a_name": "Auditoria",
        "role_b_name": "Domain Admins",
        "severity": "high",
        "risk_description": "Auditor pode modificar logs que ele mesmo auditará",
        "remediation_suggestion": "Manter contas separadas para auditoria e administração",
    },
    {
        "name": "RH Folha de Pagamento + Global Admin M365",
        "role_a_name": "RH Folha de Pagamento",
        "role_b_name": "Global Admin",
        "severity": "critical",
        "risk_description": "Global Admin M365 com acesso a dados sensíveis de RH",
        "remediation_suggestion": "Remover Global Admin — usar licença separada para M365",
    },
]


async def seed_builtin_sod_rules(db: AsyncSession, tenant_id: UUID) -> int:
    """Seed das regras SoD padrão para um tenant novo."""
    from app.models.identity_governance import SodRule

    existing = await db.execute(
        select(SodRule).where(SodRule.tenant_id == tenant_id, SodRule.is_builtin.is_(True)).limit(1)
    )
    if existing.scalar_one_or_none():
        return 0   # já tem

    count = 0
    for spec in BUILTIN_SOD_RULES:
        rule = SodRule(
            tenant_id=tenant_id,
            is_builtin=True,
            enabled=True,
            **spec,
        )
        db.add(rule)
        count += 1

    await db.flush()
    await db.commit()
    return count


# ── Helpers ────────────────────────────────────────────────────────────────────

def _generate_temp_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        has_upper = any(c.isupper() for c in pwd)
        has_lower = any(c.islower() for c in pwd)
        has_digit = any(c.isdigit() for c in pwd)
        has_special = any(c in "!@#$%" for c in pwd)
        if has_upper and has_lower and has_digit and has_special:
            return pwd
