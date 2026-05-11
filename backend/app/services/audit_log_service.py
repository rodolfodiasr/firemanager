"""Hash-chained audit log service.

Every write creates an AuditLog entry whose record_hash is computed from:
    SHA-256(previous_hash + canonical JSON of the event fields)

This creates a tamper-evident chain: modifying any entry invalidates every
subsequent hash, making silent manipulation detectable.

Usage:
    await write_audit(db, action="operation.execute", user_id=..., device_id=...,
                      operation_id=..., details={...})
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.utils.integrity import compute_record_hash


async def _get_last_hash(db: AsyncSession) -> str | None:
    """Fetch the record_hash of the most recent AuditLog entry."""
    result = await db.execute(
        select(AuditLog.record_hash)
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row


async def write_audit(
    db: AsyncSession,
    action: str,
    user_id: UUID | None = None,
    device_id: UUID | None = None,
    operation_id: UUID | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Write a single hash-chained audit log entry.

    The record_hash = SHA-256(previous_hash || canonical_json(fields)).
    Chaining is best-effort: concurrent writes may break strict chain order,
    but each entry still records its previous_hash for offline verification.
    """
    previous_hash = await _get_last_hash(db)

    record_data = {
        "action": action,
        "user_id": user_id,
        "device_id": device_id,
        "operation_id": operation_id,
        "details": str(details) if details else "",
        "ip_address": ip_address or "",
    }
    record_hash = compute_record_hash(record_data, previous_hash)

    entry = AuditLog(
        user_id=user_id,
        device_id=device_id,
        operation_id=operation_id,
        action=action,
        details=details,
        ip_address=ip_address,
        record_hash=record_hash,
        previous_hash=previous_hash,
    )
    db.add(entry)
    await db.flush()
    return entry


async def verify_chain(db: AsyncSession, limit: int = 1000) -> list[dict]:
    """Verify integrity of the last N audit log entries.

    Returns a list of violations (entries where hash doesn't match recomputed value).
    An empty list means the chain is intact.
    """
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.asc())
        .limit(limit)
    )
    entries = list(result.scalars().all())
    violations: list[dict] = []

    prev_hash: str | None = None
    for entry in entries:
        record_data = {
            "action": entry.action,
            "user_id": entry.user_id,
            "device_id": entry.device_id,
            "operation_id": entry.operation_id,
            "details": str(entry.details) if entry.details else "",
            "ip_address": entry.ip_address or "",
        }
        expected_hash = compute_record_hash(record_data, entry.previous_hash)
        if expected_hash != entry.record_hash:
            violations.append({
                "id": str(entry.id),
                "action": entry.action,
                "created_at": entry.created_at.isoformat(),
                "issue": "hash_mismatch",
                "stored_hash": entry.record_hash,
                "computed_hash": expected_hash,
            })
        if prev_hash is not None and entry.previous_hash != prev_hash:
            violations.append({
                "id": str(entry.id),
                "action": entry.action,
                "created_at": entry.created_at.isoformat(),
                "issue": "chain_break",
                "expected_previous_hash": prev_hash,
                "stored_previous_hash": entry.previous_hash,
            })
        prev_hash = entry.record_hash

    return violations
