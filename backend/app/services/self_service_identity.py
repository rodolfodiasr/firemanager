"""F39 — Identidade Self-Service: reset de senha, desbloqueio e lembretes de expiração."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


_OTP_TTL_MINUTES = 10


async def request_otp(
    db: AsyncSession,
    email: str,
    tenant_id: UUID,
    action: str = "reset_password",
) -> str:
    """Gera OTP de 6 dígitos, persiste hash, retorna o OTP em plaintext (para envio por email)."""
    from sqlalchemy import text

    otp = f"{secrets.randbelow(1_000_000):06d}"
    otp_hash = hashlib.sha256(otp.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=_OTP_TTL_MINUTES)

    # Invalidar OTPs anteriores para o mesmo email + ação
    await db.execute(
        text(
            "UPDATE otp_requests SET used = true "
            "WHERE email = :email AND action = :action AND used = false AND tenant_id = :tid"
        ),
        {"email": email, "action": action, "tid": str(tenant_id)},
    )

    await db.execute(
        text(
            "INSERT INTO otp_requests (tenant_id, email, otp_hash, action, expires_at) "
            "VALUES (:tid, :email, :hash, :action, :exp)"
        ),
        {"tid": str(tenant_id), "email": email, "hash": otp_hash, "action": action, "exp": expires_at},
    )
    await db.commit()
    return otp


async def verify_otp(
    db: AsyncSession,
    email: str,
    tenant_id: UUID,
    otp_plaintext: str,
    action: str = "reset_password",
) -> bool:
    """Valida OTP e marca como usado. Retorna True se válido."""
    from sqlalchemy import text

    otp_hash = hashlib.sha256(otp_plaintext.encode()).hexdigest()
    now = datetime.now(timezone.utc)

    result = await db.execute(
        text(
            "SELECT id FROM otp_requests "
            "WHERE email = :email AND tenant_id = :tid AND action = :action "
            "AND otp_hash = :hash AND used = false AND expires_at > :now "
            "LIMIT 1"
        ),
        {"email": email, "tid": str(tenant_id), "action": action, "hash": otp_hash, "now": now},
    )
    row = result.one_or_none()
    if not row:
        return False

    await db.execute(
        text("UPDATE otp_requests SET used = true WHERE id = :id"),
        {"id": str(row[0])},
    )
    await db.commit()
    return True


async def self_service_reset_password(
    db: AsyncSession,
    email: str,
    tenant_id: UUID,
    otp_plaintext: str,
    new_password: str,
    connector_id: UUID,
) -> dict:
    """Valida OTP + redefine senha via AD Tool Kit."""
    from app.models.identity_governance import IdentityConnector
    from app.utils.crypto import decrypt_credentials
    from app.services import local_ad_service as ldap
    from app.services.audit_log_service import write_audit

    if not await verify_otp(db, email, tenant_id, otp_plaintext, action="reset_password"):
        return {"success": False, "error": "OTP inválido ou expirado"}

    result = await db.execute(
        select(IdentityConnector).where(
            IdentityConnector.id == connector_id,
            IdentityConnector.tenant_id == tenant_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        return {"success": False, "error": "Conector AD não encontrado"}

    config = decrypt_credentials(conn.config_encrypted)
    user = await ldap.find_user(config, email)
    if not user:
        return {"success": False, "error": "Usuário não encontrado no AD"}

    await ldap.reset_password(config, user["dn"], new_password)

    await write_audit(
        db=db,
        tenant_id=tenant_id,
        user_id=None,
        action="self_service_reset_password",
        resource_type="ad_user",
        resource_id=email,
        details={"email": email, "source": "self_service"},
    )

    return {"success": True, "message": "Senha redefinida com sucesso. Faça login com a nova senha."}


async def self_service_unlock_account(
    db: AsyncSession,
    email: str,
    tenant_id: UUID,
    otp_plaintext: str,
    connector_id: UUID,
) -> dict:
    """Valida OTP + desbloqueia conta AD."""
    from app.models.identity_governance import IdentityConnector
    from app.utils.crypto import decrypt_credentials
    from app.services import local_ad_service as ldap
    from app.services.audit_log_service import write_audit

    if not await verify_otp(db, email, tenant_id, otp_plaintext, action="unlock_account"):
        return {"success": False, "error": "OTP inválido ou expirado"}

    result = await db.execute(
        select(IdentityConnector).where(
            IdentityConnector.id == connector_id,
            IdentityConnector.tenant_id == tenant_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        return {"success": False, "error": "Conector AD não encontrado"}

    config = decrypt_credentials(conn.config_encrypted)
    user = await ldap.find_user(config, email)
    if not user:
        return {"success": False, "error": "Usuário não encontrado no AD"}

    await ldap.enable_user(config, user["dn"])

    await write_audit(
        db=db,
        tenant_id=tenant_id,
        user_id=None,
        action="self_service_unlock_account",
        resource_type="ad_user",
        resource_id=email,
        details={"email": email, "source": "self_service"},
    )

    return {"success": True, "message": "Conta desbloqueada. Faça login normalmente."}
