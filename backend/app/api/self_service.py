"""API F39 — Identidade Self-Service (reset, desbloqueio, OTP, lembretes)."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


class OtpRequestBody(BaseModel):
    email: str
    tenant_id: UUID
    connector_id: UUID
    action: str = "reset_password"


class OtpVerifyResetBody(BaseModel):
    email: str
    tenant_id: UUID
    connector_id: UUID
    otp: str
    new_password: str


class OtpVerifyUnlockBody(BaseModel):
    email: str
    tenant_id: UUID
    connector_id: UUID
    otp: str


@router.post("/otp/request")
async def request_otp(
    body: OtpRequestBody,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Gera e envia OTP por email para reset de senha ou desbloqueio."""
    from app.services.self_service_identity import request_otp as _request_otp

    otp = await _request_otp(db, body.email, body.tenant_id, body.action)

    # Enviar por email (best-effort)
    try:
        from app.services.email_notifier import send_email
        subject = "Código de verificação — Eternity SecOps"
        body_text = (
            f"Seu código de verificação é: {otp}\n\n"
            f"Válido por 10 minutos. Não compartilhe este código.\n\n"
            f"Se você não solicitou isso, ignore este email."
        )
        await send_email(to=body.email, subject=subject, body=body_text)
    except Exception:
        pass   # email failure não bloqueia (retornar erro seria vazar que o email existe)

    return {"sent": True, "expires_in_minutes": 10}


@router.post("/password/reset")
async def reset_password(
    body: OtpVerifyResetBody,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Verifica OTP e redefine a senha AD."""
    if len(body.new_password) < 8:
        raise HTTPException(400, "A nova senha deve ter ao menos 8 caracteres")

    from app.services.self_service_identity import self_service_reset_password
    result = await self_service_reset_password(
        db, body.email, body.tenant_id, body.otp, body.new_password, body.connector_id
    )
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Falha ao redefinir senha"))
    return result


@router.post("/account/unlock")
async def unlock_account(
    body: OtpVerifyUnlockBody,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Verifica OTP e desbloqueia conta AD."""
    from app.services.self_service_identity import self_service_unlock_account
    result = await self_service_unlock_account(
        db, body.email, body.tenant_id, body.otp, body.connector_id
    )
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Falha ao desbloquear conta"))
    return result
