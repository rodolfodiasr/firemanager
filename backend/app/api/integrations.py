from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    TenantContext,
    User,
    get_current_user,
    get_tenant_context,
    oauth2_scheme,
    require_super_admin,
    require_tenant_admin,
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


# ── BookStack browser response schemas ────────────────────────────────────────

class BSBookItem(BaseModel):
    id: int
    name: str
    slug: str

class BSChapterItem(BaseModel):
    id: int
    name: str
    slug: str

class BSPageItem(BaseModel):
    id: int
    name: str
    slug: str

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


# ── BookStack browser helpers (for frontend dropdowns) ────────────────────────

async def _get_bookstack_integration(db: AsyncSession, integration_id: UUID) -> dict:
    from sqlalchemy import select
    from app.models.integration import Integration
    result = await db.execute(select(Integration).where(
        Integration.id == integration_id,
        Integration.type == IntegrationType.bookstack,
        Integration.is_active.is_(True),
    ))
    intg = result.scalar_one_or_none()
    if not intg:
        raise HTTPException(status_code=404, detail="Integração BookStack não encontrada ou inativa")
    return decrypt_credentials(intg.encrypted_config)


@router.get("/{integration_id}/bookstack/books", response_model=list[BSBookItem])
async def bookstack_list_books(
    integration_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[BSBookItem]:
    """List all books available in this BookStack instance."""
    from app.connectors.bookstack import connector_from_config
    config = await _get_bookstack_integration(db, integration_id)
    connector = connector_from_config(config)
    books = await connector.list_books()
    return [BSBookItem(id=b.id, name=b.name, slug=b.slug) for b in books]


@router.get("/{integration_id}/bookstack/chapters/{book_id}", response_model=list[BSChapterItem])
async def bookstack_list_chapters(
    integration_id: UUID,
    book_id: int,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[BSChapterItem]:
    """List chapters inside a specific book."""
    from app.connectors.bookstack import connector_from_config
    config = await _get_bookstack_integration(db, integration_id)
    connector = connector_from_config(config)
    chapters = await connector.list_chapters(book_id)
    return [BSChapterItem(id=ch.id, name=ch.name, slug=ch.slug) for ch in chapters]


@router.get("/{integration_id}/bookstack/pages/{chapter_id}", response_model=list[BSPageItem])
async def bookstack_list_pages(
    integration_id: UUID,
    chapter_id: int,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[BSPageItem]:
    """List pages inside a specific chapter."""
    from app.connectors.bookstack import connector_from_config
    config = await _get_bookstack_integration(db, integration_id)
    connector = connector_from_config(config)
    pages = await connector.list_pages_in_chapter(chapter_id)
    return [BSPageItem(id=p.id, name=p.name, slug=p.slug) for p in pages]


# ── BookStack re-index (manual trigger) ──────────────────────────────────────

@router.post("/{integration_id}/bookstack/reindex", status_code=202)
async def bookstack_reindex(
    integration_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Trigger an immediate BookStack re-indexing for this integration (admin only).

    Dispatches the Celery task asynchronously and returns immediately.
    Use GET /integrations to monitor; check Celery logs for progress.
    """
    from sqlalchemy import select
    from app.models.integration import Integration
    from app.workers.bookstack_index import run_bookstack_indexing

    result = await db.execute(select(Integration).where(
        Integration.id == integration_id,
        Integration.type == IntegrationType.bookstack,
    ))
    intg = result.scalar_one_or_none()
    if not intg:
        raise HTTPException(status_code=404, detail="Integração BookStack não encontrada")
    if intg.tenant_id not in (ctx.tenant.id, None):
        raise HTTPException(status_code=403, detail="Sem acesso a esta integração")

    run_bookstack_indexing.delay()
    return {"message": "Reindexação iniciada em background. Acompanhe pelos logs do Celery."}
