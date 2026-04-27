from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    TenantContext,
    User,
    get_current_user,
    get_tenant_context,
    oauth2_scheme,
    require_super_admin,
)
from app.database import get_db
from app.models.integration import IntegrationType
from app.schemas.integration import IntegrationCreate, IntegrationRead, IntegrationUpdate, TestResult
from app.services.integration_service import (
    create_integration,
    delete_integration,
    list_integrations,
    test_integration,
    update_integration,
)
from app.utils.crypto import decrypt_credentials

router = APIRouter()


def _caller_info(token: str, user: User, ctx: TenantContext | None) -> tuple[UUID | None, bool]:
    """Return (tenant_id, is_super_admin) from token context."""
    is_super = user.is_super_admin and ctx is None
    tenant_id = ctx.tenant.id if ctx else None
    return tenant_id, is_super


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[IntegrationRead])
async def get_integrations(
    token:   Annotated[str, Depends(oauth2_scheme)],
    db:      Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> list[IntegrationRead]:
    """Super admin sees global integrations. Tenant users see global + tenant."""
    from app.api.auth import _decode_token
    payload = _decode_token(token)
    is_super = bool(payload.get("super")) and current.is_super_admin
    tid_str = payload.get("tenant_id")
    tenant_id = UUID(tid_str) if tid_str else None

    rows = await list_integrations(db, tenant_id=tenant_id, is_super_admin=is_super)
    return [IntegrationRead(**r) for r in rows]


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=IntegrationRead, status_code=201)
async def add_integration(
    data:    IntegrationCreate,
    token:   Annotated[str, Depends(oauth2_scheme)],
    db:      Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> IntegrationRead:
    from app.api.auth import _decode_token
    payload = _decode_token(token)
    is_super = bool(payload.get("super")) and current.is_super_admin
    tid_str = payload.get("tenant_id")
    caller_tenant = UUID(tid_str) if tid_str else None

    # Only super admin can create global (tenant_id=None) integrations
    if data.tenant_id is None and not is_super:
        raise HTTPException(status_code=403, detail="Apenas super admin pode criar integrações globais")

    # Tenant users can only create for their own tenant
    if data.tenant_id and not is_super and data.tenant_id != caller_tenant:
        raise HTTPException(status_code=403, detail="Sem acesso a este tenant")

    target_tenant = data.tenant_id if data.tenant_id else (None if is_super else caller_tenant)

    row = await create_integration(
        db,
        data_type=data.type,
        name=data.name,
        config=data.config,
        tenant_id=target_tenant,
        is_active=data.is_active,
    )
    return IntegrationRead(**row)


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch("/{integration_id}", response_model=IntegrationRead)
async def patch_integration(
    integration_id: UUID,
    data:    IntegrationUpdate,
    token:   Annotated[str, Depends(oauth2_scheme)],
    db:      Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> IntegrationRead:
    from app.api.auth import _decode_token
    payload = _decode_token(token)
    is_super = bool(payload.get("super")) and current.is_super_admin
    tid_str = payload.get("tenant_id")
    caller_tenant = UUID(tid_str) if tid_str else None

    try:
        row = await update_integration(
            db,
            integration_id=integration_id,
            name=data.name,
            config=data.config,
            is_active=data.is_active,
            caller_tenant_id=caller_tenant,
            is_super_admin=is_super,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Integração não encontrada")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Sem acesso a esta integração")
    return IntegrationRead(**row)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{integration_id}", status_code=204)
async def remove_integration(
    integration_id: UUID,
    token:   Annotated[str, Depends(oauth2_scheme)],
    db:      Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> None:
    from app.api.auth import _decode_token
    payload = _decode_token(token)
    is_super = bool(payload.get("super")) and current.is_super_admin
    tid_str = payload.get("tenant_id")
    caller_tenant = UUID(tid_str) if tid_str else None

    try:
        await delete_integration(db, integration_id, caller_tenant, is_super)
    except ValueError:
        raise HTTPException(status_code=404, detail="Integração não encontrada")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Sem acesso a esta integração")


# ── Test ──────────────────────────────────────────────────────────────────────

@router.post("/{integration_id}/test", response_model=TestResult)
async def run_test(
    integration_id: UUID,
    token:   Annotated[str, Depends(oauth2_scheme)],
    db:      Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> TestResult:
    from sqlalchemy import select
    from app.models.integration import Integration
    from app.api.auth import _decode_token

    payload = _decode_token(token)
    is_super = bool(payload.get("super")) and current.is_super_admin
    tid_str = payload.get("tenant_id")
    caller_tenant = UUID(tid_str) if tid_str else None

    result = await db.execute(select(Integration).where(Integration.id == integration_id))
    intg = result.scalar_one_or_none()
    if not intg:
        raise HTTPException(status_code=404, detail="Integração não encontrada")
    if not is_super and intg.tenant_id not in (caller_tenant, None):
        raise HTTPException(status_code=403, detail="Sem acesso")

    config = decrypt_credentials(intg.encrypted_config)
    result_data = await test_integration(intg.type, config)
    return TestResult(**result_data)
