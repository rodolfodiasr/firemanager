"""F49 — GLPI Plugin Widget: endpoint que emite JWT de curta duração para o widget embed."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.glpi_integration import GlpiIntegration

router = APIRouter()

WIDGET_TOKEN_TTL_MINUTES = 20


class WidgetTokenCreate(BaseModel):
    object_type: str
    object_id: int | None = None
    glpi_integration_id: UUID | None = None


class WidgetTokenRead(BaseModel):
    token: str
    expires_at: datetime
    widget_url: str


@router.post("/token", response_model=WidgetTokenRead)
async def create_widget_token(
    data: WidgetTokenCreate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WidgetTokenRead:
    from app.models.glpi_widget import GlpiWidgetToken

    if data.object_type not in ("Ticket", "Computer", "Problem", "Change"):
        raise HTTPException(status_code=400, detail="object_type inválido.")

    if data.glpi_integration_id:
        intg_result = await db.execute(
            select(GlpiIntegration).where(
                GlpiIntegration.id == data.glpi_integration_id,
                GlpiIntegration.tenant_id == ctx.tenant.id,
            )
        )
        if not intg_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Integração GLPI não encontrada.")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=WIDGET_TOKEN_TTL_MINUTES)

    widget_token = GlpiWidgetToken(
        tenant_id=ctx.tenant.id,
        glpi_integration_id=data.glpi_integration_id,
        token_hash=token_hash,
        object_type=data.object_type,
        object_id=data.object_id,
        created_by=ctx.user.id,
        expires_at=expires_at,
    )
    db.add(widget_token)
    await db.flush()
    await db.commit()

    from app.config import settings
    base = getattr(settings, "public_url", "").rstrip("/") or ""
    widget_url = f"{base}/glpi-widget/{data.object_type}/{data.object_id or 0}?token={raw_token}"

    return WidgetTokenRead(token=raw_token, expires_at=expires_at, widget_url=widget_url)


@router.get("/{object_type}/{object_id}", response_class=HTMLResponse)
async def widget_view(
    object_type: str,
    object_id: int,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    from app.models.glpi_widget import GlpiWidgetToken

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(
        select(GlpiWidgetToken).where(GlpiWidgetToken.token_hash == token_hash)
    )
    wt = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if not wt or wt.expires_at.replace(tzinfo=timezone.utc) < now:
        return HTMLResponse("<html><body><p style='color:red'>Token inválido ou expirado.</p></body></html>", status_code=401)

    if not wt.used_at:
        wt.used_at = now
        await db.flush()
        await db.commit()

    html = _render_widget_html(object_type, object_id, str(wt.tenant_id))
    return HTMLResponse(html)


def _render_widget_html(object_type: str, object_id: int, tenant_id: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Eternity SecOps — {object_type} #{object_id}</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>body{{font-family:Inter,sans-serif;background:#f9fafb;margin:0;padding:12px}}</style>
</head>
<body>
<div id="app" data-object-type="{object_type}" data-object-id="{object_id}" data-tenant-id="{tenant_id}">
  <div class="flex items-center gap-2 mb-3">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
    <span class="font-semibold text-gray-800 text-sm">Eternity SecOps</span>
    <span class="ml-auto text-xs text-gray-400">{object_type} #{object_id}</span>
  </div>
  <div id="widget-content" class="space-y-3">
    <div class="animate-pulse bg-gray-200 rounded h-16"></div>
    <div class="animate-pulse bg-gray-200 rounded h-10"></div>
  </div>
</div>
<script>
(async function() {{
  const tenantId = '{tenant_id}';
  const objectType = '{object_type}';
  const objectId = {object_id};

  // Minimal widget: show device status if object_type=Computer, ticket context if Ticket
  const el = document.getElementById('widget-content');

  // Placeholder — full React bundle would be loaded in production
  el.innerHTML = `
    <div class="bg-white rounded-lg border border-gray-200 p-3">
      <p class="text-xs text-gray-500 mb-1">Contexto Eternity SecOps</p>
      <p class="text-sm font-medium text-gray-800">${{objectType}} <span class="text-indigo-600">#${{objectId}}</span></p>
      <p class="text-xs text-gray-400 mt-1">Widget carregado · Tenant ${{tenantId.substring(0,8)}}…</p>
    </div>
    <div class="flex gap-2">
      <a href="#" class="flex-1 text-center text-xs bg-indigo-600 text-white rounded-lg py-2 hover:bg-indigo-700 transition-colors">
        Abrir Chat IA
      </a>
      <a href="#" class="flex-1 text-center text-xs bg-gray-100 text-gray-700 rounded-lg py-2 hover:bg-gray-200 transition-colors">
        Ver Dispositivo
      </a>
    </div>
  `;
}})();
</script>
</body>
</html>"""
