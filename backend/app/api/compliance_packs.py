"""API F30 — Compliance Enterprise: packs, assessments, BC/DR, SLA."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_module_reviewer
from app.database import get_db
from app.services import compliance_packs_service as svc

router = APIRouter()
_require_admin = require_module_reviewer("compliance")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ControlRead(BaseModel):
    id: UUID
    control_id: str
    title: str
    category: str | None
    severity: str
    verification_type: str
    evidence_hint: str | None
    sort_order: int
    model_config = {"from_attributes": True}


class PackRead(BaseModel):
    id: UUID
    name: str
    framework: str
    version: str | None
    description: str | None
    is_builtin: bool
    is_active: bool
    controls: list[ControlRead] = []
    model_config = {"from_attributes": True}


class PackSummary(BaseModel):
    id: UUID
    name: str
    framework: str
    version: str | None
    description: str | None
    is_builtin: bool
    control_count: int = 0
    model_config = {"from_attributes": True}

    @classmethod
    def from_pack(cls, pack) -> "PackSummary":
        return cls(
            id=pack.id,
            name=pack.name,
            framework=pack.framework,
            version=pack.version,
            description=pack.description,
            is_builtin=pack.is_builtin,
            control_count=len(pack.controls),
        )


class AssessmentFindingUpdate(BaseModel):
    control_id: str
    status: str
    evidence: str = ""
    notes: str = ""


class AssessmentCreate(BaseModel):
    pack_id: UUID
    name: str


class AssessmentRead(BaseModel):
    id: UUID
    tenant_id: UUID
    pack_id: UUID | None
    pack_name: str
    name: str
    status: str
    overall_score: float | None
    compliant_count: int
    partial_count: int
    non_compliant_count: int
    total_controls: int
    findings: list | None
    started_at: object
    completed_at: object | None
    model_config = {"from_attributes": True}


class BcdrPlanCreate(BaseModel):
    name: str
    description: str | None = None
    rto_hours: int = 4
    rpo_hours: int = 1
    scope: str | None = None
    contacts: list | None = None
    recovery_steps: list | None = None
    status: str = "draft"


class BcdrPlanRead(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    rto_hours: int
    rpo_hours: int
    scope: str | None
    contacts: list | None
    recovery_steps: list | None
    last_test_at: object | None
    last_test_result: str | None
    last_test_notes: str | None
    status: str
    created_at: object
    updated_at: object
    model_config = {"from_attributes": True}


class BcdrTestRecord(BaseModel):
    result: str
    notes: str = ""


class SlaConfigRead(BaseModel):
    id: UUID
    tier_name: str
    response_minutes: int
    resolution_hours: int
    escalation_hours: int | None
    is_active: bool
    model_config = {"from_attributes": True}


class SlaConfigUpdate(BaseModel):
    response_minutes: int | None = None
    resolution_hours: int | None = None
    escalation_hours: int | None = None
    is_active: bool | None = None


# ── Packs ─────────────────────────────────────────────────────────────────────

@router.get("/packs", response_model=list[PackSummary])
async def list_packs(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PackSummary]:
    packs = await svc.list_packs(db)
    return [PackSummary.from_pack(p) for p in packs]


@router.get("/packs/{pack_id}", response_model=PackRead)
async def get_pack(
    pack_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PackRead:
    pack = await svc.get_pack(db, pack_id)
    if not pack:
        raise HTTPException(404, "Pack não encontrado")
    return PackRead.model_validate(pack)


@router.post("/packs/seed", status_code=201)
async def seed_packs(
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    created = await svc.seed_builtin_packs(db)
    return {"created": created}


# ── Assessments ───────────────────────────────────────────────────────────────

@router.get("/assessments", response_model=list[AssessmentRead])
async def list_assessments(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AssessmentRead]:
    items = await svc.list_assessments(db, ctx.tenant.id, limit=limit)
    return [AssessmentRead.model_validate(a) for a in items]


@router.post("/assessments", response_model=AssessmentRead, status_code=201)
async def create_assessment(
    body: AssessmentCreate,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssessmentRead:
    try:
        obj = await svc.create_assessment(db, ctx.tenant.id, body.pack_id, body.name, ctx.user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return AssessmentRead.model_validate(obj)


@router.get("/assessments/{assessment_id}", response_model=AssessmentRead)
async def get_assessment(
    assessment_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssessmentRead:
    obj = await svc.get_assessment(db, ctx.tenant.id, assessment_id)
    if not obj:
        raise HTTPException(404, "Assessment não encontrado")
    return AssessmentRead.model_validate(obj)


@router.patch("/assessments/{assessment_id}/finding", response_model=AssessmentRead)
async def update_finding(
    assessment_id: UUID,
    body: AssessmentFindingUpdate,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssessmentRead:
    obj = await svc.get_assessment(db, ctx.tenant.id, assessment_id)
    if not obj:
        raise HTTPException(404, "Assessment não encontrado")
    obj = await svc.update_assessment_finding(db, obj, body.control_id, body.status, body.evidence, body.notes)
    return AssessmentRead.model_validate(obj)


@router.post("/assessments/{assessment_id}/complete", response_model=AssessmentRead)
async def complete_assessment(
    assessment_id: UUID,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssessmentRead:
    obj = await svc.get_assessment(db, ctx.tenant.id, assessment_id)
    if not obj:
        raise HTTPException(404, "Assessment não encontrado")
    obj = await svc.complete_assessment(db, obj)
    return AssessmentRead.model_validate(obj)


# ── BC/DR Plans ───────────────────────────────────────────────────────────────

@router.get("/bcdr", response_model=list[BcdrPlanRead])
async def list_bcdr(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[BcdrPlanRead]:
    items = await svc.list_bcdr_plans(db, ctx.tenant.id)
    return [BcdrPlanRead.model_validate(p) for p in items]


@router.post("/bcdr", response_model=BcdrPlanRead, status_code=201)
async def create_bcdr(
    body: BcdrPlanCreate,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BcdrPlanRead:
    obj = await svc.create_bcdr_plan(db, ctx.tenant.id, body.model_dump())
    return BcdrPlanRead.model_validate(obj)


@router.get("/bcdr/{plan_id}", response_model=BcdrPlanRead)
async def get_bcdr(
    plan_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BcdrPlanRead:
    obj = await svc.get_bcdr_plan(db, ctx.tenant.id, plan_id)
    if not obj:
        raise HTTPException(404, "Plano BC/DR não encontrado")
    return BcdrPlanRead.model_validate(obj)


@router.patch("/bcdr/{plan_id}", response_model=BcdrPlanRead)
async def update_bcdr(
    plan_id: UUID,
    body: BcdrPlanCreate,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BcdrPlanRead:
    obj = await svc.get_bcdr_plan(db, ctx.tenant.id, plan_id)
    if not obj:
        raise HTTPException(404, "Plano BC/DR não encontrado")
    obj = await svc.update_bcdr_plan(db, obj, body.model_dump(exclude_unset=True))
    return BcdrPlanRead.model_validate(obj)


@router.delete("/bcdr/{plan_id}", status_code=204, response_model=None)
async def delete_bcdr(
    plan_id: UUID,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    obj = await svc.get_bcdr_plan(db, ctx.tenant.id, plan_id)
    if not obj:
        raise HTTPException(404, "Plano BC/DR não encontrado")
    await db.delete(obj)
    await db.commit()


@router.post("/bcdr/{plan_id}/test", response_model=BcdrPlanRead)
async def record_test(
    plan_id: UUID,
    body: BcdrTestRecord,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BcdrPlanRead:
    obj = await svc.get_bcdr_plan(db, ctx.tenant.id, plan_id)
    if not obj:
        raise HTTPException(404, "Plano BC/DR não encontrado")
    obj = await svc.record_bcdr_test(db, obj, body.result, body.notes)
    return BcdrPlanRead.model_validate(obj)


# ── SLA Configs ───────────────────────────────────────────────────────────────

@router.get("/sla", response_model=list[SlaConfigRead])
async def get_sla(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SlaConfigRead]:
    items = await svc.get_sla_configs(db, ctx.tenant.id)
    return [SlaConfigRead.model_validate(s) for s in items]


@router.post("/sla/seed", status_code=201)
async def seed_sla(
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    created = await svc.seed_sla_defaults(db, ctx.tenant.id)
    return {"created": len(created)}


@router.put("/sla/{tier_name}", response_model=SlaConfigRead)
async def upsert_sla(
    tier_name: str,
    body: SlaConfigUpdate,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SlaConfigRead:
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    obj = await svc.upsert_sla_config(db, ctx.tenant.id, tier_name, data)
    return SlaConfigRead.model_validate(obj)
