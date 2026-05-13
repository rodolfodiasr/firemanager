"""F38 — Cloud Security Posture Management API."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_tenant_admin
from app.database import get_db
from app.models.cspm import CloudAccount, CloudSecurityFinding, CloudResource

router = APIRouter()

CtxDep = Annotated[TenantContext, Depends(get_tenant_context)]
DbDep = Annotated[AsyncSession, Depends(get_db)]
AdminDep = Annotated[TenantContext, Depends(require_tenant_admin)]

_VALID_PROVIDERS = {"aws", "azure", "gcp"}


# ── Schemas ───────────────────────────────────────────────────────────────────

class CloudAccountCreate(BaseModel):
    name: str
    provider: str
    credentials: dict = {}
    region: str | None = None


class CloudAccountRead(BaseModel):
    id: str
    name: str
    provider: str
    region: str | None
    is_active: bool
    last_sync_at: str | None
    last_sync_status: str | None
    created_at: str

    @classmethod
    def from_orm(cls, a: CloudAccount) -> "CloudAccountRead":
        return cls(
            id=str(a.id),
            name=a.name,
            provider=a.provider,
            region=a.region,
            is_active=a.is_active,
            last_sync_at=a.last_sync_at.isoformat() if a.last_sync_at else None,
            last_sync_status=a.last_sync_status,
            created_at=a.created_at.isoformat(),
        )


class FindingRead(BaseModel):
    id: str
    account_id: str
    resource_type: str
    resource_id: str
    resource_name: str | None
    check_id: str
    check_title: str
    severity: str
    status: str
    detected_at: str

    @classmethod
    def from_orm(cls, f: CloudSecurityFinding) -> "FindingRead":
        return cls(
            id=str(f.id),
            account_id=str(f.account_id),
            resource_type=f.resource_type,
            resource_id=f.resource_id,
            resource_name=f.resource_name,
            check_id=f.check_id,
            check_title=f.check_title,
            severity=f.severity,
            status=f.status,
            detected_at=f.detected_at.isoformat(),
        )


class ResourceRead(BaseModel):
    id: str
    account_id: str
    resource_type: str
    resource_id: str
    resource_name: str | None
    region: str | None
    risk_score: int | None
    synced_at: str

    @classmethod
    def from_orm(cls, r: CloudResource) -> "ResourceRead":
        return cls(
            id=str(r.id),
            account_id=str(r.account_id),
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            resource_name=r.resource_name,
            region=r.region,
            risk_score=r.risk_score,
            synced_at=r.synced_at.isoformat(),
        )


class AcceptFindingRequest(BaseModel):
    reason: str


# ── Cloud Accounts CRUD ───────────────────────────────────────────────────────

@router.get("", response_model=list[CloudAccountRead])
async def list_accounts(ctx: CtxDep, db: DbDep) -> list[CloudAccountRead]:
    rows = (await db.execute(
        select(CloudAccount)
        .where(CloudAccount.tenant_id == ctx.tenant.id)
        .order_by(CloudAccount.created_at)
    )).scalars().all()
    return [CloudAccountRead.from_orm(r) for r in rows]


@router.post("", response_model=CloudAccountRead, status_code=201)
async def create_account(body: CloudAccountCreate, ctx: AdminDep, db: DbDep) -> CloudAccountRead:
    if body.provider not in _VALID_PROVIDERS:
        raise HTTPException(400, f"provider inválido. Use: {', '.join(_VALID_PROVIDERS)}")

    from app.utils.crypto import encrypt_credentials
    creds_enc = encrypt_credentials(body.credentials) if body.credentials else None

    account = CloudAccount(
        tenant_id=ctx.tenant.id,
        name=body.name,
        provider=body.provider,
        credentials_encrypted=creds_enc,
        region=body.region,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    await db.commit()
    return CloudAccountRead.from_orm(account)


@router.get("/{account_id}", response_model=CloudAccountRead)
async def get_account(account_id: UUID, ctx: CtxDep, db: DbDep) -> CloudAccountRead:
    a = await _get(account_id, ctx.tenant.id, db)
    return CloudAccountRead.from_orm(a)


@router.patch("/{account_id}", response_model=CloudAccountRead)
async def update_account(account_id: UUID, body: CloudAccountCreate, ctx: AdminDep, db: DbDep) -> CloudAccountRead:
    a = await _get(account_id, ctx.tenant.id, db)
    if body.provider not in _VALID_PROVIDERS:
        raise HTTPException(400, "provider inválido")

    from app.utils.crypto import encrypt_credentials
    a.name = body.name
    a.provider = body.provider
    a.region = body.region
    if body.credentials:
        a.credentials_encrypted = encrypt_credentials(body.credentials)
    await db.flush()
    await db.refresh(a)
    await db.commit()
    return CloudAccountRead.from_orm(a)


@router.delete("/{account_id}", status_code=204, response_model=None)
async def delete_account(account_id: UUID, ctx: AdminDep, db: DbDep) -> None:
    a = await _get(account_id, ctx.tenant.id, db)
    a.is_active = False
    await db.commit()


@router.post("/{account_id}/sync", status_code=202)
async def sync_account(account_id: UUID, ctx: AdminDep, db: DbDep) -> dict:
    """Dispara sync síncrono — para produção usar Celery task."""
    a = await _get(account_id, ctx.tenant.id, db)
    from app.services.cspm_service import sync_account as _sync
    result = await _sync(db, a)
    return result


# ── Findings ──────────────────────────────────────────────────────────────────

@router.get("/findings/list", response_model=list[FindingRead])
async def list_findings(
    ctx: CtxDep,
    db: DbDep,
    severity: str | None = None,
    status: str | None = None,
    account_id: UUID | None = None,
    limit: int = 100,
) -> list[FindingRead]:
    stmt = select(CloudSecurityFinding).where(CloudSecurityFinding.tenant_id == ctx.tenant.id)
    if severity:
        stmt = stmt.where(CloudSecurityFinding.severity == severity)
    if status:
        stmt = stmt.where(CloudSecurityFinding.status == status)
    if account_id:
        stmt = stmt.where(CloudSecurityFinding.account_id == account_id)
    stmt = stmt.order_by(CloudSecurityFinding.detected_at.desc()).limit(min(limit, 500))
    rows = (await db.execute(stmt)).scalars().all()
    return [FindingRead.from_orm(r) for r in rows]


@router.post("/findings/{finding_id}/accept", response_model=FindingRead)
async def accept_finding(finding_id: UUID, body: AcceptFindingRequest, ctx: AdminDep, db: DbDep) -> FindingRead:
    f = await _get_finding(finding_id, ctx.tenant.id, db)
    from app.services.cspm_service import accept_finding as _accept
    f = await _accept(db, f, ctx.user.id, body.reason)
    return FindingRead.from_orm(f)


@router.post("/findings/{finding_id}/resolve", response_model=FindingRead)
async def resolve_finding(finding_id: UUID, ctx: AdminDep, db: DbDep) -> FindingRead:
    f = await _get_finding(finding_id, ctx.tenant.id, db)
    from app.services.cspm_service import resolve_finding as _resolve
    f = await _resolve(db, f)
    return FindingRead.from_orm(f)


# ── Resources ─────────────────────────────────────────────────────────────────

@router.get("/{account_id}/resources", response_model=list[ResourceRead])
async def list_resources(account_id: UUID, ctx: CtxDep, db: DbDep) -> list[ResourceRead]:
    await _get(account_id, ctx.tenant.id, db)
    rows = (await db.execute(
        select(CloudResource)
        .where(CloudResource.account_id == account_id)
        .order_by(CloudResource.synced_at.desc())
    )).scalars().all()
    return [ResourceRead.from_orm(r) for r in rows]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get(account_id: UUID, tenant_id: UUID, db: AsyncSession) -> CloudAccount:
    a = (await db.execute(
        select(CloudAccount).where(
            CloudAccount.id == account_id,
            CloudAccount.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "Conta cloud não encontrada")
    return a


async def _get_finding(finding_id: UUID, tenant_id: UUID, db: AsyncSession) -> CloudSecurityFinding:
    f = (await db.execute(
        select(CloudSecurityFinding).where(
            CloudSecurityFinding.id == finding_id,
            CloudSecurityFinding.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if not f:
        raise HTTPException(404, "Finding não encontrado")
    return f
