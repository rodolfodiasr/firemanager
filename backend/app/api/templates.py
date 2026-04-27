"""Templates API — built-in + custom rule templates for direct SSH execution."""
import fnmatch
import json
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models.rule_template import RuleTemplate
from app.models.user import User, UserRole

router = APIRouter()

_BUILTIN_DIR = Path(__file__).parent.parent / "templates"


def _load_builtins() -> list[dict]:
    templates: list[dict] = []
    if not _BUILTIN_DIR.exists():
        return templates
    for path in sorted(_BUILTIN_DIR.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["is_builtin"] = True
            data["id"] = data["slug"]
            templates.append(data)
        except Exception:
            pass
    return templates


def _firmware_matches(pattern: str, firmware: str | None) -> bool:
    if pattern == "*" or not firmware:
        return True
    return fnmatch.fnmatch(firmware, pattern)


# ── Schemas ───────────────────────────────────────────────────────────────────

class TemplateRead(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    category: str
    vendor: str
    firmware_pattern: str
    parameters: list[dict]
    ssh_commands: list[str]
    is_builtin: bool
    is_active: bool = True


class TemplateCreate(BaseModel):
    slug: str
    name: str
    description: str = ""
    category: str
    vendor: str
    firmware_pattern: str = "*"
    parameters: list[dict] = []
    ssh_commands: list[str]


class RenderRequest(BaseModel):
    params: dict[str, str]
    device_id: UUID
    description: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[TemplateRead])
async def list_templates(
    vendor: str | None = None,
    category: str | None = None,
    firmware: str | None = None,
    _: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> list[TemplateRead]:
    builtins = _load_builtins()

    result = await db.execute(select(RuleTemplate).where(RuleTemplate.is_active == True))
    custom = [
        {
            "id": str(t.id),
            "slug": t.slug,
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "vendor": t.vendor,
            "firmware_pattern": t.firmware_pattern,
            "parameters": t.parameters,
            "ssh_commands": t.ssh_commands,
            "is_builtin": False,
            "is_active": t.is_active,
        }
        for t in result.scalars().all()
    ]

    # custom templates override builtins with the same slug
    custom_slugs = {t["slug"] for t in custom}
    all_tpl = [t for t in builtins if t["slug"] not in custom_slugs] + custom

    if vendor:
        all_tpl = [t for t in all_tpl if t["vendor"].lower() == vendor.lower()]
    if category:
        all_tpl = [t for t in all_tpl if t["category"].lower() == category.lower()]
    if firmware:
        all_tpl = [t for t in all_tpl if _firmware_matches(t["firmware_pattern"], firmware)]

    return [TemplateRead(**t) for t in all_tpl]


@router.get("/{slug}", response_model=TemplateRead)
async def get_template(
    slug: str,
    _: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> TemplateRead:
    # Check custom first
    result = await db.execute(select(RuleTemplate).where(RuleTemplate.slug == slug))
    custom = result.scalar_one_or_none()
    if custom:
        return TemplateRead(
            id=str(custom.id), slug=custom.slug, name=custom.name,
            description=custom.description, category=custom.category,
            vendor=custom.vendor, firmware_pattern=custom.firmware_pattern,
            parameters=custom.parameters, ssh_commands=custom.ssh_commands,
            is_builtin=False, is_active=custom.is_active,
        )

    for t in _load_builtins():
        if t["slug"] == slug:
            return TemplateRead(**t)

    raise HTTPException(status_code=404, detail="Template não encontrado.")


@router.post("", response_model=TemplateRead, status_code=201)
async def create_template(
    data: TemplateCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TemplateRead:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Apenas administradores podem criar templates.")

    existing = await db.execute(select(RuleTemplate).where(RuleTemplate.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Slug '{data.slug}' já existe.")

    tpl = RuleTemplate(
        id=uuid4(),
        slug=data.slug, name=data.name, description=data.description,
        category=data.category, vendor=data.vendor,
        firmware_pattern=data.firmware_pattern,
        parameters=data.parameters, ssh_commands=data.ssh_commands,
        is_active=True, created_by_id=current_user.id,
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return TemplateRead(
        id=str(tpl.id), slug=tpl.slug, name=tpl.name, description=tpl.description,
        category=tpl.category, vendor=tpl.vendor, firmware_pattern=tpl.firmware_pattern,
        parameters=tpl.parameters, ssh_commands=tpl.ssh_commands,
        is_builtin=False, is_active=tpl.is_active,
    )


@router.delete("/{slug}", status_code=204)
async def delete_template(
    slug: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Apenas administradores podem excluir templates.")

    result = await db.execute(select(RuleTemplate).where(RuleTemplate.slug == slug))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template customizado não encontrado.")

    await db.delete(tpl)
    await db.commit()
