from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_module_reviewer
from app.database import get_db
from app.models.security_infra import (
    OpaEvaluation, OpaPolicy, PentestSchedule, SecurityProfile,
    VaultConfig, VaultSecretRef,
)
from app.services.security_infra_service import evaluate_policy, seed_builtin_policies

router = APIRouter()
_require_admin = require_module_reviewer("compliance")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class VaultConfigCreate(BaseModel):
    name: str
    vault_url: str
    auth_method: str = "token"
    token: Optional[str] = None
    role_id: Optional[str] = None
    secret_id: Optional[str] = None
    default_mount: str = "secret"
    namespace: Optional[str] = None


class VaultConfigRead(BaseModel):
    id: uuid.UUID
    name: str
    vault_url: str
    auth_method: str
    role_id: Optional[str]
    default_mount: str
    namespace: Optional[str]
    is_active: bool
    last_verified_at: Optional[datetime]
    last_verified_ok: Optional[bool]
    created_at: datetime
    model_config = {"from_attributes": True}


class VaultSecretRefCreate(BaseModel):
    alias: str
    vault_path: str
    vault_key: str = "value"
    description: Optional[str] = None
    category: Optional[str] = None


class VaultSecretRefRead(BaseModel):
    id: uuid.UUID
    vault_config_id: uuid.UUID
    alias: str
    vault_path: str
    vault_key: str
    description: Optional[str]
    category: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class OpaPolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    package_name: str = "eternity"
    rego_source: str
    category: Optional[str] = None


class OpaPolicyRead(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    package_name: str
    rego_source: str
    category: Optional[str]
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class OpaEvaluateRequest(BaseModel):
    input_data: dict


class OpaEvaluationRead(BaseModel):
    id: uuid.UUID
    policy_name: str
    input_data: Optional[Any]
    result: Optional[Any]
    allowed: Optional[bool]
    evaluated_at: datetime
    model_config = {"from_attributes": True}


class SecurityProfileCreate(BaseModel):
    name: str
    profile_type: str = "hardening"
    controls: Optional[dict] = None
    notes: Optional[str] = None


class SecurityProfileRead(BaseModel):
    id: uuid.UUID
    name: str
    profile_type: str
    controls: Optional[Any]
    status: str
    applied_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class PentestCreate(BaseModel):
    title: str
    scope: Optional[str] = None
    pentest_type: str = "external"
    vendor: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    report_url: Optional[str] = None
    remediation_deadline: Optional[datetime] = None


class PentestRead(BaseModel):
    id: uuid.UUID
    title: str
    scope: Optional[str]
    pentest_type: str
    vendor: Optional[str]
    scheduled_at: Optional[datetime]
    completed_at: Optional[datetime]
    status: str
    findings_critical: int
    findings_high: int
    findings_medium: int
    findings_low: int
    report_url: Optional[str]
    remediation_deadline: Optional[datetime]
    created_at: datetime
    model_config = {"from_attributes": True}


class PentestUpdate(BaseModel):
    status: Optional[str] = None
    completed_at: Optional[datetime] = None
    findings_critical: Optional[int] = None
    findings_high: Optional[int] = None
    findings_medium: Optional[int] = None
    findings_low: Optional[int] = None
    report_url: Optional[str] = None
    remediation_deadline: Optional[datetime] = None


# ── Vault Configs ─────────────────────────────────────────────────────────────

@router.get("/vault-configs", response_model=list[VaultConfigRead])
async def list_vault_configs(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    rows = await db.execute(select(VaultConfig).where(VaultConfig.tenant_id == ctx.tenant.id))
    return rows.scalars().all()


@router.post("/vault-configs", response_model=VaultConfigRead, status_code=201)
async def create_vault_config(
    body: VaultConfigCreate,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    cfg = VaultConfig(
        tenant_id=ctx.tenant.id,
        name=body.name,
        vault_url=body.vault_url,
        auth_method=body.auth_method,
        token_encrypted=body.token,
        role_id=body.role_id,
        secret_id_encrypted=body.secret_id,
        default_mount=body.default_mount,
        namespace=body.namespace,
    )
    db.add(cfg)
    await db.flush()
    await db.refresh(cfg)
    return cfg


@router.delete("/vault-configs/{config_id}", status_code=204, response_model=None)
async def delete_vault_config(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    cfg = await db.scalar(
        select(VaultConfig).where(VaultConfig.id == config_id, VaultConfig.tenant_id == ctx.tenant.id)
    )
    if not cfg:
        raise HTTPException(404, "Vault config not found")
    await db.delete(cfg)


# ── Vault Secret Refs ─────────────────────────────────────────────────────────

@router.get("/vault-configs/{config_id}/secrets", response_model=list[VaultSecretRefRead])
async def list_secret_refs(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    rows = await db.execute(
        select(VaultSecretRef).where(
            VaultSecretRef.vault_config_id == config_id,
            VaultSecretRef.tenant_id == ctx.tenant.id,
        )
    )
    return rows.scalars().all()


@router.post("/vault-configs/{config_id}/secrets", response_model=VaultSecretRefRead, status_code=201)
async def create_secret_ref(
    config_id: uuid.UUID,
    body: VaultSecretRefCreate,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    cfg = await db.scalar(
        select(VaultConfig).where(VaultConfig.id == config_id, VaultConfig.tenant_id == ctx.tenant.id)
    )
    if not cfg:
        raise HTTPException(404, "Vault config not found")
    ref = VaultSecretRef(tenant_id=ctx.tenant.id, vault_config_id=config_id, **body.model_dump())
    db.add(ref)
    await db.flush()
    await db.refresh(ref)
    return ref


@router.delete("/vault-configs/{config_id}/secrets/{ref_id}", status_code=204, response_model=None)
async def delete_secret_ref(
    config_id: uuid.UUID,
    ref_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    ref = await db.scalar(
        select(VaultSecretRef).where(
            VaultSecretRef.id == ref_id, VaultSecretRef.tenant_id == ctx.tenant.id
        )
    )
    if not ref:
        raise HTTPException(404, "Secret ref not found")
    await db.delete(ref)


# ── OPA Policies ──────────────────────────────────────────────────────────────

@router.get("/opa-policies", response_model=list[OpaPolicyRead])
async def list_opa_policies(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    rows = await db.execute(select(OpaPolicy).where(OpaPolicy.tenant_id == ctx.tenant.id))
    return rows.scalars().all()


@router.post("/opa-policies/seed", response_model=list[OpaPolicyRead])
async def seed_policies(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    return await seed_builtin_policies(db, ctx.tenant.id, ctx.user.id)


@router.post("/opa-policies", response_model=OpaPolicyRead, status_code=201)
async def create_opa_policy(
    body: OpaPolicyCreate,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    policy = OpaPolicy(tenant_id=ctx.tenant.id, created_by=ctx.user.id, **body.model_dump())
    db.add(policy)
    await db.flush()
    await db.refresh(policy)
    return policy


@router.post("/opa-policies/{policy_id}/evaluate", response_model=OpaEvaluationRead)
async def evaluate_opa_policy(
    policy_id: uuid.UUID,
    body: OpaEvaluateRequest,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = ...,
):
    policy = await db.scalar(
        select(OpaPolicy).where(
            OpaPolicy.id == policy_id,
            OpaPolicy.tenant_id == ctx.tenant.id,
            OpaPolicy.is_active == True,
        )
    )
    if not policy:
        raise HTTPException(404, "Policy not found or inactive")
    return await evaluate_policy(db, ctx.tenant.id, policy, body.input_data, ctx.user.id)


@router.delete("/opa-policies/{policy_id}", status_code=204, response_model=None)
async def delete_opa_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    policy = await db.scalar(
        select(OpaPolicy).where(OpaPolicy.id == policy_id, OpaPolicy.tenant_id == ctx.tenant.id)
    )
    if not policy:
        raise HTTPException(404, "Policy not found")
    await db.delete(policy)


# ── Security Profiles ─────────────────────────────────────────────────────────

@router.get("/security-profiles", response_model=list[SecurityProfileRead])
async def list_security_profiles(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    rows = await db.execute(select(SecurityProfile).where(SecurityProfile.tenant_id == ctx.tenant.id))
    return rows.scalars().all()


@router.post("/security-profiles", response_model=SecurityProfileRead, status_code=201)
async def create_security_profile(
    body: SecurityProfileCreate,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    profile = SecurityProfile(tenant_id=ctx.tenant.id, **body.model_dump())
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile


@router.patch("/security-profiles/{profile_id}", response_model=SecurityProfileRead)
async def update_security_profile(
    profile_id: uuid.UUID,
    body: SecurityProfileCreate,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    profile = await db.scalar(
        select(SecurityProfile).where(
            SecurityProfile.id == profile_id, SecurityProfile.tenant_id == ctx.tenant.id
        )
    )
    if not profile:
        raise HTTPException(404, "Profile not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(profile, k, v)
    await db.flush()
    await db.refresh(profile)
    return profile


@router.post("/security-profiles/{profile_id}/apply", response_model=SecurityProfileRead)
async def apply_security_profile(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    profile = await db.scalar(
        select(SecurityProfile).where(
            SecurityProfile.id == profile_id, SecurityProfile.tenant_id == ctx.tenant.id
        )
    )
    if not profile:
        raise HTTPException(404, "Profile not found")
    profile.status = "applied"
    profile.applied_at = datetime.utcnow()
    profile.applied_by = ctx.user.id
    await db.flush()
    await db.refresh(profile)
    return profile


@router.delete("/security-profiles/{profile_id}", status_code=204, response_model=None)
async def delete_security_profile(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    profile = await db.scalar(
        select(SecurityProfile).where(
            SecurityProfile.id == profile_id, SecurityProfile.tenant_id == ctx.tenant.id
        )
    )
    if not profile:
        raise HTTPException(404, "Profile not found")
    await db.delete(profile)


# ── Pentest Schedules ─────────────────────────────────────────────────────────

@router.get("/pentest-schedules", response_model=list[PentestRead])
async def list_pentest_schedules(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    rows = await db.execute(
        select(PentestSchedule).where(PentestSchedule.tenant_id == ctx.tenant.id)
    )
    return rows.scalars().all()


@router.post("/pentest-schedules", response_model=PentestRead, status_code=201)
async def create_pentest(
    body: PentestCreate,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    pentest = PentestSchedule(tenant_id=ctx.tenant.id, created_by=ctx.user.id, **body.model_dump())
    db.add(pentest)
    await db.flush()
    await db.refresh(pentest)
    return pentest


@router.patch("/pentest-schedules/{pentest_id}", response_model=PentestRead)
async def update_pentest(
    pentest_id: uuid.UUID,
    body: PentestUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    pentest = await db.scalar(
        select(PentestSchedule).where(
            PentestSchedule.id == pentest_id, PentestSchedule.tenant_id == ctx.tenant.id
        )
    )
    if not pentest:
        raise HTTPException(404, "Pentest not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(pentest, k, v)
    await db.flush()
    await db.refresh(pentest)
    return pentest


@router.delete("/pentest-schedules/{pentest_id}", status_code=204, response_model=None)
async def delete_pentest(
    pentest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    pentest = await db.scalar(
        select(PentestSchedule).where(
            PentestSchedule.id == pentest_id, PentestSchedule.tenant_id == ctx.tenant.id
        )
    )
    if not pentest:
        raise HTTPException(404, "Pentest not found")
    await db.delete(pentest)
