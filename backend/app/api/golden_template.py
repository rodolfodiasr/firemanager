"""API routes for Fase 17 — Golden Config Templates."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_reviewer
from app.database import get_db
from app.models.device import Device
from app.models.golden_template import GoldenTemplate, GoldenTemplateVersion
from app.schemas.golden_template import (
    ApplyRequest,
    ApplyResponse,
    DivergenceRequest,
    DivergenceResponse,
    DivergenceItem,
    GoldenTemplateCreate,
    GoldenTemplateRead,
    GoldenTemplateSummary,
    GoldenTemplateUpdate,
    GoldenTemplateVersionRead,
    PrefillResponse,
    RenderRequest,
    RenderResponse,
)
from app.services.golden_template_service import (
    SYSTEM_TEMPLATES,
    compute_divergence,
    fetch_live_config,
    render_template,
    resolve_device_variables,
)

router = APIRouter()


def _to_summary(t: GoldenTemplate) -> GoldenTemplateSummary:
    return GoldenTemplateSummary(
        id=str(t.id),
        tenant_id=str(t.tenant_id) if t.tenant_id else None,
        name=t.name,
        description=t.description,
        vendor=t.vendor,
        category=t.category,
        variable_count=len(t.variables or []),
        version=t.version,
        is_system=t.is_system,
        created_at=t.created_at.isoformat(),
        updated_at=t.updated_at.isoformat(),
    )


def _sys_to_summary(t: dict) -> GoldenTemplateSummary:
    return GoldenTemplateSummary(
        id=t["id"],
        tenant_id=None,
        name=t["name"],
        description=t.get("description"),
        vendor=t["vendor"],
        category=t["category"],
        variable_count=len(t.get("variables", [])),
        version=t["version"],
        is_system=True,
        created_at=t["created_at"],
        updated_at=t["updated_at"],
    )


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[GoldenTemplateSummary])
async def list_templates(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[GoldenTemplateSummary]:
    rows = await db.execute(
        select(GoldenTemplate)
        .where(GoldenTemplate.tenant_id == ctx.tenant.id, GoldenTemplate.is_active == True)
        .order_by(GoldenTemplate.created_at.desc())
    )
    tenant_items = [_to_summary(r) for r in rows.scalars().all()]
    sys_items = [_sys_to_summary(t) for t in SYSTEM_TEMPLATES]
    return sys_items + tenant_items


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=GoldenTemplateRead, status_code=201)
async def create_template(
    data: GoldenTemplateCreate,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> GoldenTemplateRead:
    tpl = GoldenTemplate(
        tenant_id=ctx.tenant.id,
        name=data.name,
        description=data.description,
        vendor=data.vendor,
        category=data.category,
        variables=[v.model_dump() for v in data.variables],
        content=data.content,
        version=1,
        is_system=False,
        created_by_id=ctx.user.id,
    )
    db.add(tpl)
    await db.flush()
    await db.refresh(tpl)

    # Save initial version snapshot
    ver = GoldenTemplateVersion(
        template_id=tpl.id,
        version=1,
        content=data.content,
        variables=[v.model_dump() for v in data.variables],
        change_note=data.change_note or "Versão inicial",
        changed_by_id=ctx.user.id,
    )
    db.add(ver)
    await db.commit()
    await db.refresh(tpl)
    return GoldenTemplateRead.model_validate(tpl)


# ── Get ───────────────────────────────────────────────────────────────────────

@router.get("/{template_id}", response_model=GoldenTemplateRead)
async def get_template(
    template_id: str,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> GoldenTemplateRead:
    # Check system templates first
    from app.services.golden_template_service import get_system_template, SYSTEM_TEMPLATES
    sys_tpl = get_system_template(template_id)
    if sys_tpl:
        from datetime import datetime, timezone
        return GoldenTemplateRead(
            id=UUID(int=0),  # placeholder
            tenant_id=None,
            name=sys_tpl["name"],
            description=sys_tpl.get("description"),
            vendor=sys_tpl["vendor"],
            category=sys_tpl["category"],
            variables=sys_tpl.get("variables", []),
            content=sys_tpl["content"],
            version=sys_tpl["version"],
            is_active=True,
            is_system=True,
            created_at=datetime.fromisoformat(sys_tpl["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(sys_tpl["updated_at"].replace("Z", "+00:00")),
        )

    try:
        uid = UUID(template_id)
    except ValueError:
        raise HTTPException(404, "Template não encontrado")

    tpl = await db.get(GoldenTemplate, uid)
    if not tpl or tpl.tenant_id != ctx.tenant.id or not tpl.is_active:
        raise HTTPException(404, "Template não encontrado")
    return GoldenTemplateRead.model_validate(tpl)


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{template_id}", response_model=GoldenTemplateRead)
async def update_template(
    template_id: UUID,
    data: GoldenTemplateUpdate,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> GoldenTemplateRead:
    tpl = await db.get(GoldenTemplate, template_id)
    if not tpl or tpl.tenant_id != ctx.tenant.id or not tpl.is_active:
        raise HTTPException(404, "Template não encontrado")
    if tpl.is_system:
        raise HTTPException(403, "Templates de sistema não podem ser editados. Duplique-o primeiro.")

    if data.name is not None:
        tpl.name = data.name
    if data.description is not None:
        tpl.description = data.description
    if data.vendor is not None:
        tpl.vendor = data.vendor
    if data.category is not None:
        tpl.category = data.category
    if data.variables is not None:
        tpl.variables = [v.model_dump() for v in data.variables]
    if data.content is not None:
        tpl.content = data.content

    tpl.version += 1

    ver = GoldenTemplateVersion(
        template_id=tpl.id,
        version=tpl.version,
        content=tpl.content,
        variables=tpl.variables,
        change_note=data.change_note or f"Versão {tpl.version}",
        changed_by_id=ctx.user.id,
    )
    db.add(ver)
    await db.commit()
    await db.refresh(tpl)
    return GoldenTemplateRead.model_validate(tpl)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    tpl = await db.get(GoldenTemplate, template_id)
    if not tpl or tpl.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Template não encontrado")
    if tpl.is_system:
        raise HTTPException(403, "Templates de sistema não podem ser excluídos.")
    tpl.is_active = False
    await db.commit()


# ── Version history ───────────────────────────────────────────────────────────

@router.get("/{template_id}/versions", response_model=list[GoldenTemplateVersionRead])
async def list_versions(
    template_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[GoldenTemplateVersionRead]:
    tpl = await db.get(GoldenTemplate, template_id)
    if not tpl or tpl.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Template não encontrado")

    rows = await db.execute(
        select(GoldenTemplateVersion)
        .where(GoldenTemplateVersion.template_id == template_id)
        .order_by(GoldenTemplateVersion.version.desc())
    )
    return [GoldenTemplateVersionRead.model_validate(v) for v in rows.scalars().all()]


@router.post("/{template_id}/versions/{version}/restore", response_model=GoldenTemplateRead)
async def restore_version(
    template_id: UUID,
    version: int,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> GoldenTemplateRead:
    tpl = await db.get(GoldenTemplate, template_id)
    if not tpl or tpl.tenant_id != ctx.tenant.id or tpl.is_system:
        raise HTTPException(404, "Template não encontrado")

    row = await db.execute(
        select(GoldenTemplateVersion)
        .where(
            GoldenTemplateVersion.template_id == template_id,
            GoldenTemplateVersion.version == version,
        )
    )
    ver = row.scalar_one_or_none()
    if not ver:
        raise HTTPException(404, f"Versão {version} não encontrada")

    tpl.content = ver.content
    tpl.variables = ver.variables
    tpl.version += 1

    new_ver = GoldenTemplateVersion(
        template_id=tpl.id,
        version=tpl.version,
        content=tpl.content,
        variables=tpl.variables,
        change_note=f"Restaurado da versão {version}",
        changed_by_id=ctx.user.id,
    )
    db.add(new_ver)
    await db.commit()
    await db.refresh(tpl)
    return GoldenTemplateRead.model_validate(tpl)


# ── Fork (duplicate system template) ─────────────────────────────────────────

@router.post("/{template_id}/fork", response_model=GoldenTemplateRead, status_code=201)
async def fork_template(
    template_id: str,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> GoldenTemplateRead:
    from app.services.golden_template_service import get_system_template

    sys_tpl = get_system_template(template_id)
    if sys_tpl:
        source_name = sys_tpl["name"]
        source_vendor = sys_tpl["vendor"]
        source_category = sys_tpl["category"]
        source_variables = sys_tpl.get("variables", [])
        source_content = sys_tpl["content"]
    else:
        try:
            uid = UUID(template_id)
        except ValueError:
            raise HTTPException(404, "Template não encontrado")
        orig = await db.get(GoldenTemplate, uid)
        if not orig or orig.tenant_id != ctx.tenant.id:
            raise HTTPException(404, "Template não encontrado")
        source_name = orig.name
        source_vendor = orig.vendor
        source_category = orig.category
        source_variables = orig.variables
        source_content = orig.content

    tpl = GoldenTemplate(
        tenant_id=ctx.tenant.id,
        name=f"Cópia de {source_name}",
        vendor=source_vendor,
        category=source_category,
        variables=source_variables,
        content=source_content,
        version=1,
        is_system=False,
        created_by_id=ctx.user.id,
    )
    db.add(tpl)
    await db.flush()
    await db.refresh(tpl)

    ver = GoldenTemplateVersion(
        template_id=tpl.id,
        version=1,
        content=source_content,
        variables=source_variables,
        change_note=f"Duplicado de '{source_name}'",
        changed_by_id=ctx.user.id,
    )
    db.add(ver)
    await db.commit()
    await db.refresh(tpl)
    return GoldenTemplateRead.model_validate(tpl)


# ── Render preview ────────────────────────────────────────────────────────────

@router.post("/{template_id}/render", response_model=RenderResponse)
async def render_preview(
    template_id: str,
    data: RenderRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> RenderResponse:
    from app.services.golden_template_service import get_system_template

    sys_tpl = get_system_template(template_id)
    if sys_tpl:
        content = sys_tpl["content"]
    else:
        try:
            uid = UUID(template_id)
        except ValueError:
            raise HTTPException(404, "Template não encontrado")
        tpl = await db.get(GoldenTemplate, uid)
        if not tpl or tpl.tenant_id != ctx.tenant.id:
            raise HTTPException(404, "Template não encontrado")
        content = tpl.content

    rendered, unresolved = render_template(content, data.variable_values)
    return RenderResponse(content=rendered, unresolved=unresolved)


# ── Prefill variables from device ─────────────────────────────────────────────

@router.get("/{template_id}/prefill", response_model=PrefillResponse)
async def prefill_variables(
    template_id: str,
    device_id: str,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> PrefillResponse:
    device = await db.get(Device, UUID(device_id))
    if not device or device.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Dispositivo não encontrado")

    resolved = await resolve_device_variables(device, db)

    # Also add device-specific auto-fills
    resolved.setdefault("BRANCH_NAME", device.name)

    return PrefillResponse(variable_values=resolved)


# ── Divergence ────────────────────────────────────────────────────────────────

@router.post("/{template_id}/divergence", response_model=DivergenceResponse)
async def compute_template_divergence(
    template_id: str,
    data: DivergenceRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> DivergenceResponse:
    from app.services.golden_template_service import get_system_template

    sys_tpl = get_system_template(template_id)
    if sys_tpl:
        content = sys_tpl["content"]
        vendor = sys_tpl["vendor"]
    else:
        try:
            uid = UUID(template_id)
        except ValueError:
            raise HTTPException(404, "Template não encontrado")
        tpl = await db.get(GoldenTemplate, uid)
        if not tpl or tpl.tenant_id != ctx.tenant.id:
            raise HTTPException(404, "Template não encontrado")
        content = tpl.content
        vendor = tpl.vendor

    device = await db.get(Device, UUID(data.device_id))
    if not device or device.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Dispositivo não encontrado")

    rendered, unresolved = render_template(content, data.variable_values)

    from app.connectors.factory import CLI_VENDORS
    if device.vendor not in CLI_VENDORS:
        return DivergenceResponse(
            device_id=data.device_id,
            template_id=template_id,
            vendor=vendor,
            items=[],
            summary={"missing": 0, "extra": 0},
            rendered_preview=rendered,
            supported=False,
            message="Divergência automática disponível apenas para dispositivos SSH/CLI. Aplique e compare manualmente.",
        )

    live_config = await fetch_live_config(device)
    if live_config is None:
        return DivergenceResponse(
            device_id=data.device_id,
            template_id=template_id,
            vendor=vendor,
            items=[],
            summary={"missing": 0, "extra": 0},
            rendered_preview=rendered,
            supported=True,
            message="Não foi possível conectar ao dispositivo para buscar a configuração atual.",
        )

    raw_items = compute_divergence(rendered, live_config)
    items = [DivergenceItem(**i) for i in raw_items]
    missing = sum(1 for i in items if i.status == "missing")
    extra = sum(1 for i in items if i.status == "extra")

    return DivergenceResponse(
        device_id=data.device_id,
        template_id=template_id,
        vendor=vendor,
        items=items,
        summary={"missing": missing, "extra": extra, "total": len(items)},
        rendered_preview=rendered,
        supported=True,
    )


# ── Apply ─────────────────────────────────────────────────────────────────────

@router.post("/{template_id}/apply", response_model=ApplyResponse)
async def apply_template(
    template_id: str,
    data: ApplyRequest,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> ApplyResponse:
    from app.services.golden_template_service import get_system_template
    from app.connectors.factory import CLI_VENDORS, get_ssh_connector

    sys_tpl = get_system_template(template_id)
    if sys_tpl:
        content = sys_tpl["content"]
    else:
        try:
            uid = UUID(template_id)
        except ValueError:
            raise HTTPException(404, "Template não encontrado")
        tpl = await db.get(GoldenTemplate, uid)
        if not tpl or tpl.tenant_id != ctx.tenant.id:
            raise HTTPException(404, "Template não encontrado")
        content = tpl.content

    device = await db.get(Device, UUID(data.device_id))
    if not device or device.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Dispositivo não encontrado")

    rendered, unresolved = render_template(content, data.variable_values)
    if unresolved:
        raise HTTPException(422, f"Variáveis não preenchidas: {', '.join(unresolved)}")

    if device.vendor not in CLI_VENDORS:
        return ApplyResponse(
            status="manual",
            message="Dispositivo REST — aplique os comandos manualmente.",
            commands=rendered,
        )

    commands = [c for c in rendered.splitlines() if c.strip() and not c.strip().startswith(("!", "#"))]

    try:
        conn = get_ssh_connector(device)
        import asyncio
        result = await asyncio.wait_for(conn.execute_commands(commands), timeout=60)
        if result.success:
            return ApplyResponse(
                status="applied",
                message=f"Template aplicado com sucesso em {device.name}.",
                output=result.output[:3000] if result.output else None,
            )
        return ApplyResponse(
            status="error",
            message=f"Erro ao aplicar template: {result.error}",
            output=result.output[:3000] if result.output else None,
        )
    except Exception as exc:
        return ApplyResponse(status="error", message=str(exc))
