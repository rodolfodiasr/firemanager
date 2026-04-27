from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import _create_token, require_super_admin
from app.database import get_db
from app.models.device import Device, DeviceStatus
from app.models.operation import Operation, OperationStatus
from app.models.tenant import Tenant
from app.models.user import User

router = APIRouter()

SUPPORT_TOKEN_TTL = timedelta(hours=2)


class TenantOverview(BaseModel):
    id: str
    name: str
    slug: str
    device_count: int
    online_count: int
    pending_ops: int
    last_seen: str | None


class SupportTokenResponse(BaseModel):
    access_token: str
    tenant_id: str
    tenant_name: str


@router.get("/tenants/overview", response_model=list[TenantOverview])
async def get_tenants_overview(
    admin: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TenantOverview]:
    tenants_result = await db.execute(
        select(Tenant).where(Tenant.is_active == True).order_by(Tenant.name)
    )
    tenants = tenants_result.scalars().all()

    overview = []
    for tenant in tenants:
        dev_count_r = await db.execute(
            select(func.count()).select_from(Device).where(Device.tenant_id == tenant.id)
        )
        device_count = dev_count_r.scalar() or 0

        online_count_r = await db.execute(
            select(func.count()).select_from(Device).where(
                Device.tenant_id == tenant.id,
                Device.status == DeviceStatus.online,
            )
        )
        online_count = online_count_r.scalar() or 0

        pending_r = await db.execute(
            select(func.count())
            .select_from(Operation)
            .join(Device, Operation.device_id == Device.id)
            .where(
                Device.tenant_id == tenant.id,
                Operation.status.in_([
                    OperationStatus.pending,
                    OperationStatus.awaiting_approval,
                ]),
            )
        )
        pending_ops = pending_r.scalar() or 0

        last_seen_r = await db.execute(
            select(func.max(Device.last_seen)).where(Device.tenant_id == tenant.id)
        )
        last_seen = last_seen_r.scalar()

        overview.append(TenantOverview(
            id=str(tenant.id),
            name=tenant.name,
            slug=tenant.slug,
            device_count=device_count,
            online_count=online_count,
            pending_ops=pending_ops,
            last_seen=last_seen.isoformat() if last_seen else None,
        ))

    return overview


@router.post("/tenants/{tenant_id}/support-token", response_model=SupportTokenResponse)
async def create_support_token(
    tenant_id: UUID,
    admin: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SupportTokenResponse:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    token = _create_token(
        {
            "sub": str(admin.id),
            "tenant_id": str(tenant.id),
            "role": "readonly",
            "support": True,
        },
        SUPPORT_TOKEN_TTL,
    )
    return SupportTokenResponse(
        access_token=token,
        tenant_id=str(tenant.id),
        tenant_name=tenant.name,
    )
