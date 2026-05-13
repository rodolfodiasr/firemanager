"""Rotação de chave Fernet — re-encripta segredos sem alterar os valores reais.

MultiFernet([nova, antiga]) permite decriptar tokens cifrados com QUALQUER
das duas chaves. Toda re-encriptação usa APENAS a nova chave, tornando a
chave antiga obsoleta após o ciclo completo.

Campos cobertos:
  - devices.credentials_encrypted     (todas as credenciais de device)
  - identity_connectors.config_encrypted  (conectores AD/Azure/Google)
"""
from __future__ import annotations

import base64
import json
from typing import Any

from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


def _build_multifernet(new_key: str) -> tuple[MultiFernet, Fernet]:
    """Retorna (MultiFernet para leitura, Fernet para escrita)."""
    old_key = settings.credential_encryption_key
    if not old_key:
        old_key = base64.urlsafe_b64encode(b"firemanager-dev-key-32bytes-pad!").decode()
    new_fernet  = Fernet(new_key.encode() if isinstance(new_key, str) else new_key)
    old_fernet  = Fernet(old_key.encode() if isinstance(old_key, str) else old_key)
    multi       = MultiFernet([new_fernet, old_fernet])
    return multi, new_fernet


async def _reencrypt_column(
    db: AsyncSession,
    table: str,
    id_col: str,
    col: str,
    multi: MultiFernet,
    new_fernet: Fernet,
) -> tuple[int, int]:
    """Re-encripta todos os valores não-nulos de uma coluna. Retorna (ok, erros)."""
    rows = (
        await db.execute(text(f"SELECT {id_col}, {col} FROM {table} WHERE {col} IS NOT NULL"))
    ).all()

    ok = 0
    errors = 0
    for row in rows:
        row_id, ciphertext = row[0], row[1]
        if not ciphertext:
            continue
        try:
            plaintext = multi.decrypt(ciphertext.encode())
            new_cipher = new_fernet.encrypt(plaintext).decode()
            await db.execute(
                text(f"UPDATE {table} SET {col} = :c WHERE {id_col} = :id"),
                {"c": new_cipher, "id": str(row_id)},
            )
            ok += 1
        except InvalidToken:
            errors += 1
        except Exception:
            errors += 1

    return ok, errors


async def rotate_all_secrets(db: AsyncSession, new_key: str) -> dict[str, Any]:
    """Ponto de entrada principal. Re-encripta todos os campos sensíveis.

    Não faz commit — o caller (endpoint admin) é responsável pelo commit.
    """
    try:
        Fernet(new_key.encode())
    except Exception as exc:
        raise ValueError(f"Chave Fernet inválida: {exc}") from exc

    multi, new_fernet = _build_multifernet(new_key)
    results: dict[str, Any] = {}

    # Devices — campo credentials_encrypted
    dev_ok, dev_err = await _reencrypt_column(
        db, "devices", "id", "credentials_encrypted", multi, new_fernet
    )
    results["devices.credentials_encrypted"] = {"rotated": dev_ok, "errors": dev_err}

    # Identity connectors — campo config_encrypted
    ic_ok, ic_err = await _reencrypt_column(
        db, "identity_connectors", "id", "config_encrypted", multi, new_fernet
    )
    results["identity_connectors.config_encrypted"] = {"rotated": ic_ok, "errors": ic_err}

    await db.commit()

    total_ok     = dev_ok + ic_ok
    total_errors = dev_err + ic_err
    return {
        "status": "completed" if total_errors == 0 else "completed_with_errors",
        "total_rotated": total_ok,
        "total_errors": total_errors,
        "detail": results,
        "next_step": (
            "Atualize CREDENTIAL_ENCRYPTION_KEY no .env com a nova chave e reinicie o backend."
        ),
    }
