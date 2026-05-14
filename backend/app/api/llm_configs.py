"""LLM Configs API — configuração multi-provider com hierarquia global → tenant.

Rotas:
  /admin/llm-configs/*   — super admin, escopo global (tenant_id = NULL)
  /llm-configs/*         — tenant admin, escopo por tenant
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_current_user, get_tenant_context
from app.database import get_db
from app.models.user import User
from app.services import llm_config_service as svc
from app.services.llm_config_service import PROVIDER_META

admin_router = APIRouter()  # prefixo /admin/llm-configs
router = APIRouter()        # prefixo /llm-configs


# ── Schemas ───────────────────────────────────────────────────────────────────

class LLMConfigRead(BaseModel):
    id: str
    tenant_id: str | None
    provider: str
    display_name: str
    model_name: str
    api_base_url: str | None
    has_key: bool
    is_enabled: bool
    is_default: bool
    priority: int
    no_train_flag: bool
    scope: str   # "global" | "tenant"
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, c) -> "LLMConfigRead":
        return cls(
            id=str(c.id),
            tenant_id=str(c.tenant_id) if c.tenant_id else None,
            provider=c.provider,
            display_name=c.display_name,
            model_name=c.model_name,
            api_base_url=c.api_base_url,
            has_key=bool(c.api_key_encrypted),
            is_enabled=c.is_enabled,
            is_default=c.is_default,
            priority=c.priority,
            no_train_flag=c.no_train_flag,
            scope="tenant" if c.tenant_id else "global",
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )


class LLMConfigCreate(BaseModel):
    provider: str
    model_name: str
    api_key: str | None = None
    api_base_url: str | None = None
    is_default: bool = False
    no_train_flag: bool = True


class LLMConfigUpdate(BaseModel):
    model_name: str | None = None
    api_key: str | None = None
    api_base_url: str | None = None
    is_default: bool | None = None
    is_enabled: bool | None = None
    no_train_flag: bool | None = None


class TestResult(BaseModel):
    ok: bool
    message: str
    latency_ms: int


class ProviderMeta(BaseModel):
    provider: str
    label: str
    default_model: str
    needs_key: bool
    local: bool
    base_url: str | None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_super_admin(user: User) -> None:
    if not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Requer super admin.")


def _require_admin(ctx: TenantContext) -> None:
    if ctx.role.value not in ("admin",):
        raise HTTPException(status_code=403, detail="Requer role admin no tenant.")


def _validate_provider(provider: str) -> None:
    if provider not in PROVIDER_META:
        raise HTTPException(status_code=400, detail=f"Provider desconhecido: {provider}. Opções: {list(PROVIDER_META)}")


# ── Metadados públicos ────────────────────────────────────────────────────────

@admin_router.get("/providers", response_model=list[ProviderMeta])
@router.get("/providers", response_model=list[ProviderMeta])
async def list_providers() -> list[ProviderMeta]:
    """Lista todos os providers disponíveis com metadados (sem autenticação de nível)."""
    return [
        ProviderMeta(
            provider=p,
            label=m["label"],
            default_model=m["default_model"],
            needs_key=m["needs_key"],
            local=m["local"],
            base_url=m.get("base_url"),
        )
        for p, m in PROVIDER_META.items()
    ]


# ── Admin — config global (tenant_id = NULL) ──────────────────────────────────

@admin_router.get("", response_model=list[LLMConfigRead])
async def admin_list(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[LLMConfigRead]:
    _require_super_admin(user)
    configs = await svc.list_configs(db, tenant_id=None)
    return [LLMConfigRead.from_orm(c) for c in configs]


@admin_router.post("", response_model=LLMConfigRead, status_code=201)
async def admin_create(
    data: LLMConfigCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LLMConfigRead:
    _require_super_admin(user)
    _validate_provider(data.provider)
    cfg = await svc.create_config(
        db, tenant_id=None,
        provider=data.provider, model_name=data.model_name,
        api_key=data.api_key, api_base_url=data.api_base_url,
        is_default=data.is_default, no_train_flag=data.no_train_flag,
    )
    await db.commit()
    return LLMConfigRead.from_orm(cfg)


@admin_router.put("/{config_id}", response_model=LLMConfigRead)
async def admin_update(
    config_id: UUID,
    data: LLMConfigUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LLMConfigRead:
    _require_super_admin(user)
    cfg = await svc.get_config(db, config_id, tenant_id=None)
    if not cfg:
        raise HTTPException(status_code=404, detail="Config não encontrada.")
    cfg = await svc.update_config(db, cfg, data.model_name, data.api_key, data.api_base_url, data.is_default, data.is_enabled, data.no_train_flag)
    await db.commit()
    return LLMConfigRead.from_orm(cfg)


@admin_router.delete("/{config_id}", status_code=204)
async def admin_delete(
    config_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    _require_super_admin(user)
    cfg = await svc.get_config(db, config_id, tenant_id=None)
    if not cfg:
        raise HTTPException(status_code=404, detail="Config não encontrada.")
    await svc.delete_config(db, cfg)
    await db.commit()


@admin_router.post("/{config_id}/test", response_model=TestResult)
async def admin_test(
    config_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TestResult:
    _require_super_admin(user)
    cfg = await svc.get_config(db, config_id, tenant_id=None)
    if not cfg:
        raise HTTPException(status_code=404, detail="Config não encontrada.")
    result = await svc.test_connection(cfg)
    return TestResult(**result)


# ── Tenant — config por tenant ────────────────────────────────────────────────

@router.get("", response_model=list[LLMConfigRead])
async def tenant_list(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[LLMConfigRead]:
    """Lista configs do tenant + configs globais herdadas (marcadas como scope=global)."""
    tenant_cfgs = await svc.list_configs(db, tenant_id=ctx.tenant.id)
    global_cfgs = await svc.list_configs(db, tenant_id=None)
    # Configs próprias do tenant sobrepõem as globais visualmente
    return [LLMConfigRead.from_orm(c) for c in tenant_cfgs] + [LLMConfigRead.from_orm(c) for c in global_cfgs]


@router.post("", response_model=LLMConfigRead, status_code=201)
async def tenant_create(
    data: LLMConfigCreate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LLMConfigRead:
    _require_admin(ctx)
    _validate_provider(data.provider)
    cfg = await svc.create_config(
        db, tenant_id=ctx.tenant.id,
        provider=data.provider, model_name=data.model_name,
        api_key=data.api_key, api_base_url=data.api_base_url,
        is_default=data.is_default, no_train_flag=data.no_train_flag,
    )
    await db.commit()
    return LLMConfigRead.from_orm(cfg)


@router.put("/{config_id}", response_model=LLMConfigRead)
async def tenant_update(
    config_id: UUID,
    data: LLMConfigUpdate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LLMConfigRead:
    _require_admin(ctx)
    cfg = await svc.get_config(db, config_id, tenant_id=ctx.tenant.id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Config não encontrada.")
    cfg = await svc.update_config(db, cfg, data.model_name, data.api_key, data.api_base_url, data.is_default, data.is_enabled, data.no_train_flag)
    await db.commit()
    return LLMConfigRead.from_orm(cfg)


@router.delete("/{config_id}", status_code=204)
async def tenant_delete(
    config_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    _require_admin(ctx)
    cfg = await svc.get_config(db, config_id, tenant_id=ctx.tenant.id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Config não encontrada.")
    await svc.delete_config(db, cfg)
    await db.commit()


@router.post("/{config_id}/test", response_model=TestResult)
async def tenant_test(
    config_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TestResult:
    _require_admin(ctx)
    # Permite testar config própria ou herdada global
    cfg = await svc.get_config(db, config_id, tenant_id=ctx.tenant.id)
    if not cfg:
        cfg = await svc.get_config(db, config_id, tenant_id=None)
    if not cfg:
        raise HTTPException(status_code=404, detail="Config não encontrada.")
    result = await svc.test_connection(cfg)
    return TestResult(**result)


@router.get("/effective", response_model=dict)
async def tenant_effective(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Retorna qual provider será usado efetivamente para este tenant."""
    provider = await svc.resolve_provider(ctx.tenant.id, db)
    return {"provider": provider.name, "resolved": True}
