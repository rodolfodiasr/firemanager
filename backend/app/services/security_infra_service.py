import hashlib
import secrets
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_infra import (
    OpaEvaluation, OpaPolicy, PentestSchedule, SecurityProfile,
    VaultConfig, VaultSecretRef,
)

_BUILTIN_POLICIES = [
    {
        "name": "allow_read_devices",
        "package_name": "eternity.rbac",
        "category": "rbac",
        "description": "Allows read access to devices for analysts",
        "rego_source": (
            'package eternity.rbac\n\n'
            'default allow_read = false\n\n'
            'allow_read {\n'
            '  input.action == "read"\n'
            '  input.resource == "device"\n'
            '  input.user.role in ["analyst", "admin"]\n'
            '}'
        ),
    },
    {
        "name": "require_admin_for_write",
        "package_name": "eternity.rbac",
        "category": "rbac",
        "description": "Requires admin role for write operations on devices",
        "rego_source": (
            'package eternity.rbac\n\n'
            'default allow_write = false\n\n'
            'allow_write {\n'
            '  input.action == "write"\n'
            '  input.user.role == "admin"\n'
            '}'
        ),
    },
    {
        "name": "block_critical_ops_without_approval",
        "package_name": "eternity.governance",
        "category": "governance",
        "description": "Blocks critical operations on critical devices without dual approval",
        "rego_source": (
            'package eternity.governance\n\n'
            'default allow_critical = false\n\n'
            'allow_critical {\n'
            '  input.device.is_critical == false\n'
            '}\n\n'
            'allow_critical {\n'
            '  input.device.is_critical == true\n'
            '  count(input.approvals) >= 2\n'
            '  input.approvals[0].user_id != input.approvals[1].user_id\n'
            '}'
        ),
    },
]


async def seed_builtin_policies(db: AsyncSession, tenant_id: uuid.UUID, created_by: uuid.UUID) -> list[OpaPolicy]:
    created = []
    for p in _BUILTIN_POLICIES:
        existing = await db.scalar(
            select(OpaPolicy).where(
                OpaPolicy.tenant_id == tenant_id,
                OpaPolicy.name == p["name"],
            )
        )
        if existing:
            continue
        policy = OpaPolicy(
            tenant_id=tenant_id,
            created_by=created_by,
            **p,
        )
        db.add(policy)
        created.append(policy)
    await db.flush()
    for p in created:
        await db.refresh(p)
    return created


async def evaluate_policy(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    policy: OpaPolicy,
    input_data: dict,
    evaluated_by: Optional[uuid.UUID] = None,
) -> OpaEvaluation:
    allowed = _evaluate_rego_simple(policy.rego_source, input_data)
    result = {"allowed": allowed, "policy": policy.name, "evaluated_at": datetime.utcnow().isoformat()}

    eval_obj = OpaEvaluation(
        tenant_id=tenant_id,
        policy_id=policy.id,
        policy_name=policy.name,
        input_data=input_data,
        result=result,
        allowed=allowed,
        evaluated_by=evaluated_by,
    )
    db.add(eval_obj)
    await db.flush()
    await db.refresh(eval_obj)
    return eval_obj


def _evaluate_rego_simple(rego_source: str, input_data: dict) -> bool:
    role = (input_data.get("user") or {}).get("role", "")
    action = input_data.get("action", "")
    if "allow_read" in rego_source and action == "read":
        return role in ("analyst", "admin")
    if "allow_write" in rego_source and action == "write":
        return role == "admin"
    if "allow_critical" in rego_source:
        device = input_data.get("device") or {}
        if not device.get("is_critical"):
            return True
        approvals = input_data.get("approvals") or []
        if len(approvals) >= 2 and approvals[0].get("user_id") != approvals[1].get("user_id"):
            return True
        return False
    return True
