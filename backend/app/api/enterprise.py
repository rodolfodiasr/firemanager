"""Fase 25 — Enterprise Platform API: white-label branding and API keys."""
from __future__ import annotations

import hashlib
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.enterprise import ApiKey, TenantBranding

router = APIRouter()

CtxDep = Annotated[TenantContext, Depends(get_tenant_context)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns (raw_key, key_prefix, key_hash).
    raw_key  = 'fm_' + 29-char url-safe token  (~40 chars total)
    key_prefix = first 8 chars (shown in UI)
    key_hash   = SHA-256 hex digest of raw_key
    """
    raw_key = "fm_" + secrets.token_urlsafe(29)
    key_prefix = raw_key[:8]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_prefix, key_hash


# ── Schemas ────────────────────────────────────────────────────────────────────

class BrandingRead(BaseModel):
    id: str | None = None
    tenant_id: str
    company_name: str | None = None
    primary_color: str | None = None
    logo_url: str | None = None
    favicon_url: str | None = None

    @classmethod
    def from_orm(cls, b: TenantBranding) -> "BrandingRead":
        return cls(
            id=str(b.id),
            tenant_id=str(b.tenant_id),
            company_name=b.company_name,
            primary_color=b.primary_color,
            logo_url=b.logo_url,
            favicon_url=b.favicon_url,
        )

    @classmethod
    def defaults(cls, tenant_id: UUID) -> "BrandingRead":
        return cls(tenant_id=str(tenant_id))


class BrandingUpdate(BaseModel):
    company_name: str | None = None
    primary_color: str | None = None
    logo_url: str | None = None
    favicon_url: str | None = None


class ApiKeyRead(BaseModel):
    id: str
    tenant_id: str
    name: str
    key_prefix: str
    permissions: list[str]
    is_active: bool
    last_used_at: str | None = None
    expires_at: str | None = None
    created_at: str

    @classmethod
    def from_orm(cls, k: ApiKey) -> "ApiKeyRead":
        return cls(
            id=str(k.id),
            tenant_id=str(k.tenant_id),
            name=k.name,
            key_prefix=k.key_prefix,
            permissions=k.permissions or [],
            is_active=k.is_active,
            last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
            expires_at=k.expires_at.isoformat() if k.expires_at else None,
            created_at=k.created_at.isoformat(),
        )


class ApiKeyCreate(BaseModel):
    name: str
    permissions: list[str] = []
    expires_at: str | None = None


class ApiKeyCreated(ApiKeyRead):
    """Like ApiKeyRead but includes the full raw key — returned once on creation/rotation."""
    raw_key: str


# ── Branding endpoints ─────────────────────────────────────────────────────────

@router.get("/branding", response_model=BrandingRead)
async def get_branding(db: DbDep, ctx: CtxDep):
    """Return tenant branding config, or defaults if not yet configured."""
    row = (await db.execute(
        select(TenantBranding).where(TenantBranding.tenant_id == ctx.tenant.id)
    )).scalar_one_or_none()
    if not row:
        return BrandingRead.defaults(ctx.tenant.id)
    return BrandingRead.from_orm(row)


@router.put("/branding", response_model=BrandingRead)
async def upsert_branding(body: BrandingUpdate, db: DbDep, ctx: CtxDep):
    """Create or update tenant branding config (upsert)."""
    row = (await db.execute(
        select(TenantBranding).where(TenantBranding.tenant_id == ctx.tenant.id)
    )).scalar_one_or_none()

    if row is None:
        row = TenantBranding(tenant_id=ctx.tenant.id)
        db.add(row)

    row.company_name = body.company_name
    row.primary_color = body.primary_color
    row.logo_url = body.logo_url
    row.favicon_url = body.favicon_url

    await db.flush()
    await db.refresh(row)
    return BrandingRead.from_orm(row)


# ── API Key endpoints ──────────────────────────────────────────────────────────

@router.get("/api-keys", response_model=list[ApiKeyRead])
async def list_api_keys(db: DbDep, ctx: CtxDep):
    """List API keys for the tenant (never returns key_hash)."""
    rows = (await db.execute(
        select(ApiKey)
        .where(ApiKey.tenant_id == ctx.tenant.id)
        .order_by(ApiKey.created_at)
    )).scalars().all()
    return [ApiKeyRead.from_orm(k) for k in rows]


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=201)
async def create_api_key(body: ApiKeyCreate, db: DbDep, ctx: CtxDep):
    """Create a new API key. The full key is returned ONCE — store it securely."""
    from datetime import datetime, timezone

    raw_key, key_prefix, key_hash = _generate_api_key()

    expires_at = None
    if body.expires_at:
        try:
            expires_at = datetime.fromisoformat(body.expires_at)
        except ValueError:
            raise HTTPException(status_code=422, detail="expires_at must be ISO 8601 datetime")

    key = ApiKey(
        tenant_id=ctx.tenant.id,
        name=body.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        permissions=body.permissions,
        expires_at=expires_at,
    )
    db.add(key)
    await db.flush()
    await db.refresh(key)

    result = ApiKeyRead.from_orm(key).model_dump()
    result["raw_key"] = raw_key
    return result


@router.delete("/api-keys/{key_id}", status_code=204)
async def delete_api_key(key_id: UUID, db: DbDep, ctx: CtxDep):
    """Soft-delete an API key (sets is_active=False)."""
    key = await db.get(ApiKey, key_id)
    if not key or key.tenant_id != ctx.tenant.id:
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = False
    await db.flush()


@router.post("/api-keys/{key_id}/rotate", response_model=ApiKeyCreated)
async def rotate_api_key(key_id: UUID, db: DbDep, ctx: CtxDep):
    """Generate a new secret for an existing API key. Returns the new full key ONCE."""
    key = await db.get(ApiKey, key_id)
    if not key or key.tenant_id != ctx.tenant.id:
        raise HTTPException(status_code=404, detail="API key not found")
    if not key.is_active:
        raise HTTPException(status_code=409, detail="Cannot rotate a deactivated API key")

    raw_key, key_prefix, key_hash = _generate_api_key()
    key.key_prefix = key_prefix
    key.key_hash = key_hash

    await db.flush()
    await db.refresh(key)

    result = ApiKeyRead.from_orm(key).model_dump()
    result["raw_key"] = raw_key
    return result
