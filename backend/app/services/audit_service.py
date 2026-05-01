"""Audit service — policy checks, review submission, and operation queries."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.audit_policy import AuditPolicy
from app.models.operation import Operation, OperationStatus
from app.models.user import User, UserRole
from app.schemas.audit import AuditOperationRead

# ── System defaults: True = requires N2 approval ───────────────────────────────
_DEFAULT_REQUIRES_APPROVAL: dict[str, bool] = {
    "create_rule": True,
    "edit_rule": True,
    "delete_rule": True,
    "create_nat_policy": True,
    "delete_nat_policy": True,
    "create_route_policy": True,
    "delete_route_policy": True,
    "create_group": True,
    "configure_content_filter": True,
    "configure_app_rules": True,
    "add_security_exclusion": False,
    "toggle_gateway_av": False,
    "toggle_anti_spyware": False,
    "toggle_ips": False,
    "toggle_app_control": False,
    "toggle_geo_ip": False,
    "toggle_botnet": False,
    "toggle_dpi_ssl": False,
    # read-only — never require approval
    "list_rules": False,
    "list_nat_policies": False,
    "list_route_policies": False,
    "get_security_status": False,
    "health_check": False,
    "get_snapshot": False,
}

_READ_ONLY_INTENTS = {
    "list_rules", "list_nat_policies", "list_route_policies",
    "get_security_status", "health_check",
}


async def check_requires_approval(db: AsyncSession, user: User, intent: str) -> bool:
    """Return True if this user+intent combination requires N2 approval before execution."""
    if user.role == UserRole.admin:
        return False
    if intent in _READ_ONLY_INTENTS:
        return False

    # 1. User-specific override
    result = await db.execute(
        select(AuditPolicy).where(
            and_(
                AuditPolicy.scope_type == "user",
                AuditPolicy.scope_id == str(user.id),
                AuditPolicy.intent == intent,
            )
        )
    )
    policy = result.scalar_one_or_none()
    if policy is not None:
        return policy.requires_approval

    # 2. Role-level policy
    result = await db.execute(
        select(AuditPolicy).where(
            and_(
                AuditPolicy.scope_type == "role",
                AuditPolicy.scope_id == user.role.value,
                AuditPolicy.intent == intent,
            )
        )
    )
    policy = result.scalar_one_or_none()
    if policy is not None:
        return policy.requires_approval

    # 3. System default
    return _DEFAULT_REQUIRES_APPROVAL.get(intent, True)


async def submit_for_review(db: AsyncSession, operation_id: UUID) -> Operation:
    """Move an approved operation into the N2 review queue."""
    result = await db.execute(select(Operation).where(Operation.id == operation_id))
    operation = result.scalar_one_or_none()
    if not operation:
        raise ValueError("Operação não encontrada")
    if operation.status not in (OperationStatus.approved, OperationStatus.pending):
        raise ValueError("Operação não está em estado que permite envio para revisão")
    operation.status = OperationStatus.pending_review
    await db.flush()
    await db.refresh(operation)
    return operation


async def submit_review(
    db: AsyncSession,
    reviewer: User,
    operation_id: UUID,
    approved: bool,
    comment: str,
    reviewer_tenant_role: "TenantRole | None" = None,
    tenant_id: "UUID | None" = None,
) -> Operation:
    """N2/admin approves or denies an operation. Approval triggers execution.

    Segregation of duties rules:
    - No one may approve their own submission.
    - Analysts may only approve operations submitted by readonly users.
    - Admins may approve operations from any role.
    """
    from app.models.user_tenant_role import TenantRole, UserTenantRole

    result = await db.execute(select(Operation).where(Operation.id == operation_id))
    operation = result.scalar_one_or_none()
    if not operation:
        raise ValueError("Operação não encontrada")
    if operation.status != OperationStatus.pending_review:
        raise ValueError("Operação não está aguardando revisão")

    if operation.user_id == reviewer.id:
        raise ValueError("Não é permitido aprovar a própria operação (segregação de funções)")

    if reviewer_tenant_role == TenantRole.analyst and tenant_id:
        sub_result = await db.execute(
            select(UserTenantRole).where(
                and_(
                    UserTenantRole.user_id == operation.user_id,
                    UserTenantRole.tenant_id == tenant_id,
                )
            )
        )
        submitter_utr = sub_result.scalar_one_or_none()
        if not submitter_utr or submitter_utr.role != TenantRole.readonly:
            raise ValueError(
                "Analistas só podem aprovar solicitações de usuários com perfil Leitura. "
                "Operações de outros analistas ou administradores requerem aprovação de um administrador."
            )

    operation.reviewer_id = reviewer.id
    operation.review_comment = comment.strip() or None
    operation.reviewed_at = datetime.now(timezone.utc)

    if approved:
        # Execute the operation — import here to avoid circular imports
        from app.services.operation_service import execute_operation
        operation = await execute_operation(db, operation_id)
        # Preserve review metadata (execute_operation may flush/refresh)
        result2 = await db.execute(select(Operation).where(Operation.id == operation_id))
        operation = result2.scalar_one()
        operation.reviewer_id = reviewer.id
        operation.review_comment = comment.strip() or None
        operation.reviewed_at = datetime.now(timezone.utc)
    else:
        if not comment.strip():
            raise ValueError("Justificativa obrigatória ao negar uma operação")
        operation.status = OperationStatus.rejected

    await db.flush()
    await db.refresh(operation)
    return operation


# ── Query helpers ───────────────────────────────────────────────────────────────

async def _enrich_operations(db: AsyncSession, ops: list[Operation]) -> list[AuditOperationRead]:
    """Join user and device info for a list of operations."""
    if not ops:
        return []

    from app.models.device import Device

    Requester = aliased(User)
    Reviewer = aliased(User)

    op_ids = [op.id for op in ops]
    stmt = (
        select(
            Operation,
            Requester.name,
            Requester.email,
            Device.name,
            Device.vendor,
            Reviewer.name,
        )
        .join(Requester, Operation.user_id == Requester.id)
        .join(Device, Operation.device_id == Device.id)
        .outerjoin(Reviewer, Operation.reviewer_id == Reviewer.id)
        .where(Operation.id.in_(op_ids))
        .order_by(Operation.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()

    return [
        AuditOperationRead(
            id=op.id,
            natural_language_input=op.natural_language_input,
            intent=op.intent,
            action_plan=op.action_plan,
            status=op.status.value,
            error_message=op.error_message,
            review_comment=op.review_comment,
            reviewed_at=op.reviewed_at,
            executed_direct=op.executed_direct,
            created_at=op.created_at,
            updated_at=op.updated_at,
            requester_name=req_name,
            requester_email=req_email,
            device_name=dev_name,
            device_vendor=str(dev_vendor) if dev_vendor else None,
            reviewer_name=rev_name,
        )
        for op, req_name, req_email, dev_name, dev_vendor, rev_name in rows
    ]


async def get_pending_operations(
    db: AsyncSession,
    tenant_id: UUID | None = None,
    reviewer_role: "TenantRole | None" = None,
) -> list[AuditOperationRead]:
    from app.models.device import Device
    from app.models.user_tenant_role import TenantRole, UserTenantRole

    query = select(Operation).where(Operation.status == OperationStatus.pending_review)
    if tenant_id:
        query = query.join(Device, Operation.device_id == Device.id).where(Device.tenant_id == tenant_id)

    if reviewer_role == TenantRole.analyst:
        # Analysts only see operations submitted by readonly users
        readonly_users = select(UserTenantRole.user_id).where(
            and_(
                UserTenantRole.tenant_id == tenant_id,
                UserTenantRole.role == TenantRole.readonly,
            )
        )
        query = query.where(Operation.user_id.in_(readonly_users))

    result = await db.execute(query.order_by(Operation.created_at.desc()))
    return await _enrich_operations(db, list(result.scalars().all()))


async def get_direct_operations(db: AsyncSession, tenant_id: UUID | None = None) -> list[AuditOperationRead]:
    from app.models.device import Device
    query = select(Operation).where(
        and_(
            Operation.executed_direct == True,  # noqa: E712
            Operation.status.in_([OperationStatus.completed, OperationStatus.failed]),
        )
    )
    if tenant_id:
        query = query.join(Device, Operation.device_id == Device.id).where(Device.tenant_id == tenant_id)
    result = await db.execute(query.order_by(Operation.created_at.desc()).limit(200))
    return await _enrich_operations(db, list(result.scalars().all()))


async def get_history_operations(db: AsyncSession, tenant_id: UUID | None = None) -> list[AuditOperationRead]:
    from app.models.device import Device
    query = select(Operation).where(
        and_(
            Operation.status.in_([
                OperationStatus.completed,
                OperationStatus.failed,
                OperationStatus.rejected,
            ]),
            Operation.intent.notin_(list(_READ_ONLY_INTENTS)),
        )
    )
    if tenant_id:
        query = query.join(Device, Operation.device_id == Device.id).where(Device.tenant_id == tenant_id)
    result = await db.execute(query.order_by(Operation.created_at.desc()).limit(200))
    return await _enrich_operations(db, list(result.scalars().all()))


async def get_pending_count(
    db: AsyncSession,
    tenant_id: UUID | None = None,
    reviewer_role: "TenantRole | None" = None,
) -> int:
    from app.models.device import Device
    from app.models.user_tenant_role import TenantRole, UserTenantRole

    query = select(Operation).where(Operation.status == OperationStatus.pending_review)
    if tenant_id:
        query = query.join(Device, Operation.device_id == Device.id).where(Device.tenant_id == tenant_id)

    if reviewer_role == TenantRole.analyst:
        readonly_users = select(UserTenantRole.user_id).where(
            and_(
                UserTenantRole.tenant_id == tenant_id,
                UserTenantRole.role == TenantRole.readonly,
            )
        )
        query = query.where(Operation.user_id.in_(readonly_users))

    result = await db.execute(query)
    return len(result.scalars().all())


# ── Policy CRUD ─────────────────────────────────────────────────────────────────

async def get_all_policies(db: AsyncSession) -> list[AuditPolicy]:
    result = await db.execute(select(AuditPolicy).order_by(AuditPolicy.scope_type, AuditPolicy.scope_id))
    return list(result.scalars().all())


async def upsert_policy(
    db: AsyncSession,
    updater: User,
    scope_type: str,
    scope_id: str,
    intent: str,
    requires_approval: bool,
) -> AuditPolicy:
    result = await db.execute(
        select(AuditPolicy).where(
            and_(
                AuditPolicy.scope_type == scope_type,
                AuditPolicy.scope_id == scope_id,
                AuditPolicy.intent == intent,
            )
        )
    )
    policy = result.scalar_one_or_none()
    if policy:
        policy.requires_approval = requires_approval
        policy.updated_by = updater.id
    else:
        policy = AuditPolicy(
            scope_type=scope_type,
            scope_id=scope_id,
            intent=intent,
            requires_approval=requires_approval,
            updated_by=updater.id,
        )
        db.add(policy)
    await db.flush()
    await db.refresh(policy)
    return policy


async def delete_policy(db: AsyncSession, scope_type: str, scope_id: str, intent: str) -> None:
    result = await db.execute(
        select(AuditPolicy).where(
            and_(
                AuditPolicy.scope_type == scope_type,
                AuditPolicy.scope_id == scope_id,
                AuditPolicy.intent == intent,
            )
        )
    )
    policy = result.scalar_one_or_none()
    if policy:
        await db.delete(policy)
        await db.flush()
