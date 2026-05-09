"""Platform configuration API — manage API keys and secrets stored in DB.

All endpoints require super-admin. Values are never returned in plaintext.

Known keys:
  anthropic_api_key, anthropic_model, anthropic_max_tokens
  openai_api_key, openai_embedding_model
  smtp_host, smtp_port, smtp_user, smtp_password, email_from
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_super_admin
from app.database import get_db
from app.models.user import User
from app.services import platform_config_service

router = APIRouter()

AdminDep = Annotated[User, Depends(require_super_admin)]
DbDep = Annotated[AsyncSession, Depends(get_db)]

# Keys that are allowed to be managed via this API
ALLOWED_KEYS = {
    "anthropic_api_key": "Chave da API Anthropic (Claude)",
    "anthropic_model": "Modelo Anthropic padrão",
    "anthropic_max_tokens": "Máximo de tokens por resposta",
    "openai_api_key": "Chave da API OpenAI (embeddings)",
    "openai_embedding_model": "Modelo de embedding OpenAI",
    "smtp_host": "Servidor SMTP",
    "smtp_port": "Porta SMTP",
    "smtp_user": "Usuário SMTP",
    "smtp_password": "Senha SMTP",
    "email_from": "Endereço de envio padrão",
}


class SetKeyRequest(BaseModel):
    value: str
    description: str | None = None


class KeyMeta(BaseModel):
    key: str
    description: str | None
    is_sensitive: bool
    is_set: bool
    updated_at: str
    has_env_fallback: bool


@router.get("", response_model=list[KeyMeta])
async def list_config_keys(
    _admin: AdminDep,
    db: DbDep,
) -> list[dict[str, Any]]:
    from app.config import settings

    stored = {row["key"]: row for row in await platform_config_service.list_keys(db)}

    result = []
    for key, default_desc in ALLOWED_KEYS.items():
        env_val = getattr(settings, key, None)
        row = stored.get(key)
        result.append({
            "key": key,
            "description": (row["description"] if row else None) or default_desc,
            "is_sensitive": True,
            "is_set": bool(row and row["is_set"]),
            "updated_at": row["updated_at"] if row else "",
            "has_env_fallback": bool(env_val),
        })
    return result


@router.put("/{key}")
async def set_config_key(
    key: str,
    body: SetKeyRequest,
    _admin: AdminDep,
    db: DbDep,
) -> dict[str, str]:
    if key not in ALLOWED_KEYS:
        raise HTTPException(status_code=400, detail=f"Chave desconhecida: {key}")
    if not body.value.strip():
        raise HTTPException(status_code=422, detail="Valor não pode ser vazio")

    await platform_config_service.set_key(key, body.value.strip(), body.description, db)
    await db.commit()
    return {"status": "ok", "key": key}


@router.delete("/{key}")
async def clear_config_key(
    key: str,
    _admin: AdminDep,
    db: DbDep,
) -> dict[str, str]:
    if key not in ALLOWED_KEYS:
        raise HTTPException(status_code=400, detail=f"Chave desconhecida: {key}")

    deleted = await platform_config_service.delete_key(key, db)
    await db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Chave não encontrada no banco de dados")
    return {"status": "cleared", "key": key}


@router.post("/{key}/test")
async def test_config_key(
    key: str,
    _admin: AdminDep,
    db: DbDep,
) -> dict[str, Any]:
    if key not in ALLOWED_KEYS:
        raise HTTPException(status_code=400, detail=f"Chave desconhecida: {key}")

    value = await platform_config_service.get(key, db)
    if not value:
        return {"ok": False, "message": "Chave não configurada (nem banco nem .env)"}

    if key == "anthropic_api_key":
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=value)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return {"ok": True, "message": f"Anthropic OK — stop_reason: {msg.stop_reason}"}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    if key == "openai_api_key":
        try:
            import openai
            client = openai.OpenAI(api_key=value)
            models = client.models.list()
            return {"ok": True, "message": f"OpenAI OK — {len(list(models.data))} modelos disponíveis"}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    if key == "smtp_password":
        smtp_host = await platform_config_service.get("smtp_host", db)
        smtp_port_str = await platform_config_service.get("smtp_port", db)
        smtp_user = await platform_config_service.get("smtp_user", db)
        try:
            import smtplib
            port = int(smtp_port_str or "587")
            with smtplib.SMTP(smtp_host or "smtp.gmail.com", port, timeout=10) as s:
                s.starttls()
                s.login(smtp_user or "", value)
            return {"ok": True, "message": "SMTP autenticado com sucesso"}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    return {"ok": True, "message": f"Valor configurado ({len(value)} caracteres)"}
