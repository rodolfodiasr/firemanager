"""Fase 26 — Golden Config Bundles REST-native API."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.golden_bundle import BundleApply, BundleSection, GoldenBundle

router = APIRouter()

CtxDep = Annotated[TenantContext, Depends(get_tenant_context)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


# ── Schemas ────────────────────────────────────────────────────────────────────

class SectionIn(BaseModel):
    section_type: str
    template_id: str | None = None
    rest_payload_template: str | None = None
    apply_strategy: str = "rest_api"
    apply_order: int = 0
    rollback_strategy: str = "none"


class SectionRead(BaseModel):
    id: str
    section_type: str
    template_id: str | None
    rest_payload_template: str | None
    apply_strategy: str
    apply_order: int
    rollback_strategy: str

    @classmethod
    def from_orm(cls, s: BundleSection) -> "SectionRead":
        return cls(
            id=str(s.id),
            section_type=s.section_type,
            template_id=str(s.template_id) if s.template_id else None,
            rest_payload_template=s.rest_payload_template,
            apply_strategy=s.apply_strategy,
            apply_order=s.apply_order,
            rollback_strategy=s.rollback_strategy,
        )


class BundleCreate(BaseModel):
    name: str
    description: str | None = None
    vendor: str
    variables: dict = {}
    sections: list[SectionIn] = []


class BundleRead(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str | None
    vendor: str
    variables: dict
    sections: list[SectionRead]
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, b: GoldenBundle) -> "BundleRead":
        return cls(
            id=str(b.id),
            tenant_id=str(b.tenant_id),
            name=b.name,
            description=b.description,
            vendor=b.vendor,
            variables=b.variables or {},
            sections=[SectionRead.from_orm(s) for s in (b.sections or [])],
            created_at=b.created_at.isoformat(),
            updated_at=b.updated_at.isoformat(),
        )


class ApplyIn(BaseModel):
    device_id: str
    variables: dict = {}


class ApplyRead(BaseModel):
    id: str
    bundle_id: str
    device_id: str
    status: str
    variables_used: dict | None
    section_results: dict | None
    started_at: str
    completed_at: str | None

    @classmethod
    def from_orm(cls, a: BundleApply) -> "ApplyRead":
        return cls(
            id=str(a.id),
            bundle_id=str(a.bundle_id),
            device_id=str(a.device_id),
            status=a.status,
            variables_used=a.variables_used,
            section_results=a.section_results,
            started_at=a.started_at.isoformat(),
            completed_at=a.completed_at.isoformat() if a.completed_at else None,
        )


# ── Bundle CRUD ────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[BundleRead])
async def list_bundles(db: DbDep, ctx: CtxDep):
    rows = (await db.execute(
        select(GoldenBundle)
        .where(GoldenBundle.tenant_id == ctx.tenant.id)
        .order_by(GoldenBundle.created_at)
    )).scalars().all()
    return [BundleRead.from_orm(b) for b in rows]


@router.post("/", response_model=BundleRead, status_code=201)
async def create_bundle(body: BundleCreate, db: DbDep, ctx: CtxDep):
    bundle = GoldenBundle(
        tenant_id=ctx.tenant.id,
        name=body.name,
        description=body.description,
        vendor=body.vendor,
        variables=body.variables,
    )
    db.add(bundle)
    await db.flush()

    for sec_in in body.sections:
        section = BundleSection(
            bundle_id=bundle.id,
            section_type=sec_in.section_type,
            template_id=UUID(sec_in.template_id) if sec_in.template_id else None,
            rest_payload_template=sec_in.rest_payload_template,
            apply_strategy=sec_in.apply_strategy,
            apply_order=sec_in.apply_order,
            rollback_strategy=sec_in.rollback_strategy,
        )
        db.add(section)

    await db.flush()
    await db.refresh(bundle)
    return BundleRead.from_orm(bundle)


@router.get("/{bundle_id}", response_model=BundleRead)
async def get_bundle(bundle_id: UUID, db: DbDep, ctx: CtxDep):
    bundle = await db.get(GoldenBundle, bundle_id)
    if not bundle or bundle.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    return BundleRead.from_orm(bundle)


@router.put("/{bundle_id}", response_model=BundleRead)
async def update_bundle(bundle_id: UUID, body: BundleCreate, db: DbDep, ctx: CtxDep):
    bundle = await db.get(GoldenBundle, bundle_id)
    if not bundle or bundle.tenant_id != ctx.tenant.id:
        raise HTTPException(404)

    bundle.name = body.name
    bundle.description = body.description
    bundle.vendor = body.vendor
    bundle.variables = body.variables

    # Replace sections: delete old, insert new
    for existing_section in list(bundle.sections):
        await db.delete(existing_section)
    await db.flush()

    for sec_in in body.sections:
        section = BundleSection(
            bundle_id=bundle.id,
            section_type=sec_in.section_type,
            template_id=UUID(sec_in.template_id) if sec_in.template_id else None,
            rest_payload_template=sec_in.rest_payload_template,
            apply_strategy=sec_in.apply_strategy,
            apply_order=sec_in.apply_order,
            rollback_strategy=sec_in.rollback_strategy,
        )
        db.add(section)

    await db.flush()
    await db.refresh(bundle)
    return BundleRead.from_orm(bundle)


@router.delete("/{bundle_id}")
async def delete_bundle(bundle_id: UUID, db: DbDep, ctx: CtxDep) -> dict:
    bundle = await db.get(GoldenBundle, bundle_id)
    if not bundle or bundle.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    await db.delete(bundle)
    await db.commit()
    return {"ok": True}


# ── Apply ──────────────────────────────────────────────────────────────────────

@router.post("/{bundle_id}/apply", response_model=ApplyRead, status_code=202)
async def apply_bundle(bundle_id: UUID, body: ApplyIn, db: DbDep, ctx: CtxDep):
    bundle = await db.get(GoldenBundle, bundle_id)
    if not bundle or bundle.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Bundle not found")

    apply_rec = BundleApply(
        bundle_id=bundle_id,
        device_id=UUID(body.device_id),
        status="applying",
        variables_used=body.variables,
    )
    db.add(apply_rec)
    await db.flush()
    await db.refresh(apply_rec)

    from app.workers.bundle_apply import apply_golden_bundle
    apply_golden_bundle.delay(str(apply_rec.id))

    return ApplyRead.from_orm(apply_rec)


@router.get("/applies/{apply_id}", response_model=ApplyRead)
async def get_apply_status(apply_id: UUID, db: DbDep, ctx: CtxDep):
    apply_rec = await db.get(BundleApply, apply_id)
    if not apply_rec:
        raise HTTPException(404)
    # Verify the bundle belongs to this tenant
    bundle = await db.get(GoldenBundle, apply_rec.bundle_id)
    if not bundle or bundle.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    return ApplyRead.from_orm(apply_rec)
