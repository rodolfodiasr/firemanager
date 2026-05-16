"""Service — F33 IA Safety & Governança: dual-approval, maintenance windows, erasure, SIRP."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_safety import ApprovalRequest, ErasureRequest, MaintenanceWindow, SecurityIncident


# ── Maintenance Windows ────────────────────────────────────────────────────────

async def list_windows(
    db: AsyncSession, tenant_id: uuid.UUID, active_only: bool = False
) -> list[MaintenanceWindow]:
    q = select(MaintenanceWindow).where(MaintenanceWindow.tenant_id == tenant_id)
    if active_only:
        q = q.where(MaintenanceWindow.is_active == True)
    q = q.order_by(MaintenanceWindow.starts_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_window(
    db: AsyncSession, tenant_id: uuid.UUID, window_id: uuid.UUID
) -> MaintenanceWindow | None:
    result = await db.execute(
        select(MaintenanceWindow).where(
            MaintenanceWindow.id == window_id,
            MaintenanceWindow.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_window(
    db: AsyncSession, tenant_id: uuid.UUID, data: dict, created_by: uuid.UUID | None = None
) -> MaintenanceWindow:
    obj = MaintenanceWindow(tenant_id=tenant_id, created_by=created_by, **data)
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    await db.commit()
    return obj


async def update_window(db: AsyncSession, window: MaintenanceWindow, data: dict) -> MaintenanceWindow:
    for k, v in data.items():
        setattr(window, k, v)
    await db.flush()
    await db.refresh(window)
    await db.commit()
    return window


async def is_in_maintenance(
    db: AsyncSession, tenant_id: uuid.UUID, device_id: uuid.UUID | None = None
) -> MaintenanceWindow | None:
    """Return the active maintenance window that blocks operations now, or None."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await db.execute(
        select(MaintenanceWindow).where(
            MaintenanceWindow.tenant_id == tenant_id,
            MaintenanceWindow.is_active == True,
            MaintenanceWindow.block_ai_operations == True,
            MaintenanceWindow.starts_at <= now,
            MaintenanceWindow.ends_at >= now,
        )
    )
    windows = list(result.scalars().all())
    for w in windows:
        devices = w.affected_devices
        if not devices:
            return w
        if device_id and str(device_id) in [str(d) for d in devices]:
            return w
    return None


# ── Approval Requests ─────────────────────────────────────────────────────────

async def list_approval_requests(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    status: str | None = None,
    limit: int = 50,
) -> list[ApprovalRequest]:
    q = select(ApprovalRequest).where(ApprovalRequest.tenant_id == tenant_id)
    if status:
        q = q.where(ApprovalRequest.status == status)
    q = q.order_by(ApprovalRequest.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_approval_request(
    db: AsyncSession, tenant_id: uuid.UUID, request_id: uuid.UUID
) -> ApprovalRequest | None:
    result = await db.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.id == request_id,
            ApprovalRequest.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_approval_request(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    title: str,
    description: str | None,
    risk_level: str,
    operation_context: dict | None,
    requester_id: uuid.UUID | None,
    requester_note: str | None = None,
    requires_two: bool = True,
    ttl_hours: int = 24,
) -> ApprovalRequest:
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=ttl_hours)
    obj = ApprovalRequest(
        tenant_id=tenant_id,
        title=title,
        description=description,
        risk_level=risk_level,
        operation_context=operation_context,
        requester_id=requester_id,
        requester_note=requester_note,
        requires_two_approvals=requires_two,
        status="pending_first",
        expires_at=expires_at,
    )
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    await db.commit()
    return obj


async def approve_request(
    db: AsyncSession, req: ApprovalRequest, approver_id: uuid.UUID
) -> ApprovalRequest:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if req.status == "pending_first":
        if req.requester_id and req.requester_id == approver_id:
            raise ValueError("O solicitante não pode ser o primeiro aprovador")
        req.first_approver_id = approver_id
        req.first_approved_at = now
        if req.requires_two_approvals:
            req.status = "pending_second"
        else:
            req.status = "approved"
    elif req.status == "pending_second":
        if req.first_approver_id == approver_id:
            raise ValueError("O mesmo aprovador não pode aprovar duas vezes (four-eyes)")
        req.second_approver_id = approver_id
        req.second_approved_at = now
        req.status = "approved"
    else:
        raise ValueError(f"Solicitação não pode ser aprovada no status '{req.status}'")
    await db.flush()
    await db.refresh(req)
    await db.commit()
    return req


async def reject_request(
    db: AsyncSession, req: ApprovalRequest, approver_id: uuid.UUID, reason: str
) -> ApprovalRequest:
    req.status = "rejected"
    req.rejected_by = approver_id
    req.rejected_at = datetime.now(timezone.utc).replace(tzinfo=None)
    req.rejection_reason = reason
    await db.flush()
    await db.refresh(req)
    await db.commit()
    return req


# ── Erasure Requests (LGPD) ───────────────────────────────────────────────────

async def list_erasure_requests(
    db: AsyncSession, tenant_id: uuid.UUID, status: str | None = None
) -> list[ErasureRequest]:
    q = select(ErasureRequest).where(ErasureRequest.tenant_id == tenant_id)
    if status:
        q = q.where(ErasureRequest.status == status)
    q = q.order_by(ErasureRequest.created_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_erasure_request(
    db: AsyncSession, tenant_id: uuid.UUID, request_id: uuid.UUID
) -> ErasureRequest | None:
    result = await db.execute(
        select(ErasureRequest).where(
            ErasureRequest.id == request_id,
            ErasureRequest.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_erasure_request(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    target_email: str,
    reason: str | None,
    legal_basis: str | None,
    requested_by: uuid.UUID | None,
) -> ErasureRequest:
    obj = ErasureRequest(
        tenant_id=tenant_id,
        target_user_email=target_email,
        reason=reason,
        legal_basis=legal_basis,
        requested_by=requested_by,
        status="pending",
    )
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    await db.commit()
    return obj


async def approve_erasure(
    db: AsyncSession, req: ErasureRequest, approver_id: uuid.UUID
) -> ErasureRequest:
    req.approved_by = approver_id
    req.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    req.status = "in_progress"
    await db.flush()
    await db.refresh(req)
    await db.commit()
    return req


async def execute_erasure(
    db: AsyncSession, req: ErasureRequest
) -> ErasureRequest:
    """Execute the erasure: anonymize/delete data for the target email across audit tables."""
    from sqlalchemy import text

    target_email = req.target_user_email
    affected: list[str] = []

    # Anonymize assistant sessions
    await db.execute(
        text("""
            UPDATE assistant_sessions SET title = '[REMOVIDO - LGPD]'
            WHERE created_by IN (
                SELECT id FROM users WHERE email = :email AND tenant_id = :tid
            )
        """),
        {"email": target_email, "tid": req.tenant_id},
    )
    affected.append("assistant_sessions")

    # Anonymize audit entries (replace user field, not delete — immutable chain)
    await db.execute(
        text("""
            UPDATE audit_log SET user_email = '[removido-lgpd]'
            WHERE tenant_id = :tid AND user_email = :email
        """),
        {"tid": req.tenant_id, "email": target_email},
    )
    affected.append("audit_log")

    # Anonymize otp_requests
    await db.execute(
        text("""
            DELETE FROM otp_requests
            WHERE tenant_id = :tid AND email = :email
        """),
        {"tid": req.tenant_id, "email": target_email},
    )
    affected.append("otp_requests")

    req.status = "completed"
    req.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    req.affected_tables = affected
    req.audit_summary = {
        "anonymized_tables": affected,
        "note": "Dados pessoais anonimizados/removidos conforme LGPD Art. 18.",
    }
    await db.flush()
    await db.refresh(req)
    await db.commit()
    return req


async def reject_erasure(
    db: AsyncSession, req: ErasureRequest, approver_id: uuid.UUID, reason: str
) -> ErasureRequest:
    req.status = "rejected"
    req.rejection_reason = reason
    req.approved_by = approver_id
    req.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()
    await db.refresh(req)
    await db.commit()
    return req


# ── Security Incidents (SIRP) ─────────────────────────────────────────────────

async def list_incidents(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 100,
) -> list[SecurityIncident]:
    q = select(SecurityIncident).where(SecurityIncident.tenant_id == tenant_id)
    if status:
        q = q.where(SecurityIncident.status == status)
    if severity:
        q = q.where(SecurityIncident.severity == severity)
    q = q.order_by(SecurityIncident.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_incident(
    db: AsyncSession, tenant_id: uuid.UUID, incident_id: uuid.UUID
) -> SecurityIncident | None:
    result = await db.execute(
        select(SecurityIncident).where(
            SecurityIncident.id == incident_id,
            SecurityIncident.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_incident(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    title: str,
    description: str | None,
    severity: str,
    category: str,
    affected_systems: list[str] | None,
    reported_by: uuid.UUID | None,
) -> SecurityIncident:
    now = datetime.now(timezone.utc)
    obj = SecurityIncident(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        title=title,
        description=description,
        severity=severity,
        category=category,
        affected_systems=affected_systems,
        reported_by=reported_by,
        status="open",
        timeline=[{
            "at": now.isoformat(),
            "action": "Incidente criado",
            "user_id": str(reported_by) if reported_by else None,
            "details": f"Incidente registrado com severidade {severity}.",
        }],
    )
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    await db.commit()
    return obj


async def update_incident(
    db: AsyncSession, incident: SecurityIncident, data: dict, user_id: uuid.UUID | None = None
) -> SecurityIncident:
    changed_fields = []
    for k, v in data.items():
        if v is not None or k in ("root_cause", "remediation", "assigned_to"):
            old = getattr(incident, k, None)
            if old != v:
                setattr(incident, k, v)
                changed_fields.append(k)

    if changed_fields:
        timeline = list(incident.timeline or [])
        timeline.append({
            "at": datetime.now(timezone.utc).isoformat(),
            "action": "Incidente atualizado",
            "user_id": str(user_id) if user_id else None,
            "details": f"Campos atualizados: {', '.join(changed_fields)}.",
        })
        incident.timeline = timeline
        incident.updated_at = datetime.now(timezone.utc)

    if data.get("status") == "resolved" and not incident.resolved_at:
        incident.resolved_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(incident)
    await db.commit()
    return incident


async def add_timeline_entry(
    db: AsyncSession,
    incident: SecurityIncident,
    action: str,
    user_id: uuid.UUID | None,
    details: str = "",
) -> SecurityIncident:
    timeline = list(incident.timeline or [])
    timeline.append({
        "at": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "user_id": str(user_id) if user_id else None,
        "details": details,
    })
    incident.timeline = timeline
    incident.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(incident)
    await db.commit()
    return incident
