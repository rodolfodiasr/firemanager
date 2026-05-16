from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_module_reviewer
from app.database import get_db
from app.models.product import (
    BillingInvoice, BillingPlan, BillingSubscription,
    HelpArticle, OnboardingChecklist, UserPreference,
)
from app.services.product_service import (
    complete_step, create_subscription, get_or_create_checklist,
    get_or_create_preferences, seed_articles, seed_plans,
)

router = APIRouter()
_require_admin = require_module_reviewer("compliance")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class PlanRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    monthly_price_brl: Decimal
    max_devices: Optional[int]
    max_users: Optional[int]
    ai_token_quota: Optional[int]
    sla_target_pct: Optional[Decimal]
    features: Optional[Any]
    is_active: bool
    model_config = {"from_attributes": True}


class SubscriptionRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    status: str
    cancel_at_period_end: bool
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    trial_end: Optional[datetime]
    created_at: datetime
    plan: PlanRead
    model_config = {"from_attributes": True}


class InvoiceRead(BaseModel):
    id: uuid.UUID
    amount_brl: Decimal
    status: str
    period_start: Optional[datetime]
    period_end: Optional[datetime]
    paid_at: Optional[datetime]
    due_date: Optional[datetime]
    invoice_pdf_url: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class ChecklistRead(BaseModel):
    id: uuid.UUID
    step_add_device: bool
    step_run_snapshot: bool
    step_ask_agent: bool
    step_configure_alert: bool
    completed: bool
    skipped: bool
    completed_at: Optional[datetime]
    model_config = {"from_attributes": True}


class ChecklistStepRequest(BaseModel):
    step: str


class ArticleRead(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    category: str
    persona: Optional[str]
    content_md: str
    is_published: bool
    view_count: int
    sort_order: int
    created_at: datetime
    model_config = {"from_attributes": True}


class ArticleCreate(BaseModel):
    title: str
    slug: str
    category: str = "general"
    persona: Optional[str] = None
    content_md: str
    is_published: bool = False
    sort_order: int = 0


class UserPrefsRead(BaseModel):
    id: uuid.UUID
    language: str
    timezone: str
    theme: str
    notifications_enabled: bool
    onboarding_step: int
    onboarding_completed: bool
    model_config = {"from_attributes": True}


class UserPrefsUpdate(BaseModel):
    language: Optional[str] = None
    timezone: Optional[str] = None
    theme: Optional[str] = None
    notifications_enabled: Optional[bool] = None


# ── Billing Plans ─────────────────────────────────────────────────────────────

@router.get("/billing/plans", response_model=list[PlanRead])
async def list_plans(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = ...,
):
    rows = await db.execute(select(BillingPlan).where(BillingPlan.is_active == True))
    return rows.scalars().all()


@router.post("/billing/plans/seed", response_model=list[PlanRead])
async def seed_billing_plans(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    return await seed_plans(db)


# ── Subscription ──────────────────────────────────────────────────────────────

@router.get("/billing/subscription", response_model=Optional[SubscriptionRead])
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = ...,
):
    return await db.scalar(
        select(BillingSubscription)
        .where(BillingSubscription.tenant_id == ctx.tenant.id)
        .options(selectinload(BillingSubscription.plan))
    )


@router.post("/billing/subscription/start", response_model=SubscriptionRead)
async def start_subscription(
    plan_slug: str = "starter",
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    sub = await create_subscription(db, ctx.tenant.id, plan_slug)
    result = await db.scalar(
        select(BillingSubscription)
        .where(BillingSubscription.id == sub.id)
        .options(selectinload(BillingSubscription.plan))
    )
    return result


# ── Invoices ──────────────────────────────────────────────────────────────────

@router.get("/billing/invoices", response_model=list[InvoiceRead])
async def list_invoices(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = ...,
):
    rows = await db.execute(
        select(BillingInvoice)
        .where(BillingInvoice.tenant_id == ctx.tenant.id)
        .order_by(BillingInvoice.created_at.desc())
    )
    return rows.scalars().all()


# ── Onboarding Checklist ──────────────────────────────────────────────────────

@router.get("/onboarding/checklist", response_model=ChecklistRead)
async def get_checklist(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = ...,
):
    return await get_or_create_checklist(db, ctx.tenant.id, ctx.user.id)


@router.post("/onboarding/checklist/complete-step", response_model=ChecklistRead)
async def complete_onboarding_step(
    body: ChecklistStepRequest,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = ...,
):
    valid_steps = {"add_device", "run_snapshot", "ask_agent", "configure_alert"}
    if body.step not in valid_steps:
        raise HTTPException(400, f"Invalid step. Valid: {valid_steps}")
    checklist = await get_or_create_checklist(db, ctx.tenant.id, ctx.user.id)
    return await complete_step(db, checklist, body.step)


@router.post("/onboarding/checklist/skip", response_model=ChecklistRead)
async def skip_onboarding(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = ...,
):
    checklist = await get_or_create_checklist(db, ctx.tenant.id, ctx.user.id)
    checklist.skipped = True
    await db.flush()
    await db.refresh(checklist)
    return checklist


# ── Help Articles ─────────────────────────────────────────────────────────────

@router.get("/help/articles", response_model=list[ArticleRead])
async def list_articles(
    category: Optional[str] = None,
    persona: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = ...,
):
    q = select(HelpArticle).where(HelpArticle.is_published == True)
    if category:
        q = q.where(HelpArticle.category == category)
    if persona:
        q = q.where(HelpArticle.persona == persona)
    q = q.order_by(HelpArticle.sort_order)
    rows = await db.execute(q)
    return rows.scalars().all()


@router.get("/help/articles/{slug}", response_model=ArticleRead)
async def get_article(
    slug: str,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = ...,
):
    article = await db.scalar(
        select(HelpArticle).where(HelpArticle.slug == slug, HelpArticle.is_published == True)
    )
    if not article:
        raise HTTPException(404, "Article not found")
    article.view_count = (article.view_count or 0) + 1
    await db.flush()
    return article


@router.post("/help/articles/seed", response_model=list[ArticleRead])
async def seed_help_articles(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    return await seed_articles(db, ctx.user.id)


@router.post("/help/articles", response_model=ArticleRead, status_code=201)
async def create_help_article(
    body: ArticleCreate,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    existing = await db.scalar(select(HelpArticle).where(HelpArticle.slug == body.slug))
    if existing:
        raise HTTPException(409, "Slug already in use")
    article = HelpArticle(created_by=ctx.user.id, **body.model_dump())
    db.add(article)
    await db.flush()
    await db.refresh(article)
    return article


@router.patch("/help/articles/{article_id}", response_model=ArticleRead)
async def update_help_article(
    article_id: uuid.UUID,
    body: ArticleCreate,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    article = await db.get(HelpArticle, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(article, k, v)
    await db.flush()
    await db.refresh(article)
    return article


@router.delete("/help/articles/{article_id}", status_code=204, response_model=None)
async def delete_help_article(
    article_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    article = await db.get(HelpArticle, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    await db.delete(article)


# ── User Preferences ──────────────────────────────────────────────────────────

@router.get("/preferences", response_model=UserPrefsRead)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = ...,
):
    return await get_or_create_preferences(db, ctx.user.id)


@router.patch("/preferences", response_model=UserPrefsRead)
async def update_preferences(
    body: UserPrefsUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = ...,
):
    prefs = await get_or_create_preferences(db, ctx.user.id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(prefs, k, v)
    await db.flush()
    await db.refresh(prefs)
    return prefs


# ── Stripe Checkout ───────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan_id: str
    success_url: str = "https://app.firemanager.io/billing?success=1"
    cancel_url: str = "https://app.firemanager.io/billing?canceled=1"


@router.post("/billing/checkout")
async def create_checkout(
    body: CheckoutRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    ctx: Annotated[TenantContext, Depends(_require_admin)],
) -> dict:
    """Inicia checkout Stripe para upgrade de plano."""
    from app.services.stripe_service import create_checkout_session

    try:
        plan_uuid = uuid.UUID(body.plan_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="plan_id inválido")

    plan = await db.scalar(select(BillingPlan).where(BillingPlan.id == plan_uuid))
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado")

    try:
        url = await create_checkout_session(db, ctx.tenant, plan, body.success_url, body.cancel_url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao criar sessão Stripe: {e}")

    return {"checkout_url": url}


# ── Invoice PDF Download ──────────────────────────────────────────────────────

@router.get("/billing/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> Response:
    """Gera e retorna o PDF de uma fatura."""
    invoice = await db.scalar(
        select(BillingInvoice).where(
            BillingInvoice.id == invoice_id,
            BillingInvoice.tenant_id == ctx.tenant.id,
        )
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Fatura não encontrada")

    # Carregar subscription + plan para dados do PDF
    sub = None
    plan_name = "N/A"
    if invoice.subscription_id:
        sub = await db.scalar(
            select(BillingSubscription)
            .where(BillingSubscription.id == invoice.subscription_id)
            .options(selectinload(BillingSubscription.plan))
        )
        if sub and sub.plan:
            plan_name = sub.plan.name

    def _fmt_date(dt) -> str:
        if dt is None:
            return ""
        if hasattr(dt, "strftime"):
            return dt.strftime("%d/%m/%Y")
        return str(dt)

    invoice_data = {
        "tenant_name": ctx.tenant.name,
        "plan_name": plan_name,
        "amount_brl": float(invoice.amount_brl),
        "period_start": _fmt_date(invoice.period_start),
        "period_end": _fmt_date(invoice.period_end),
        "paid_at": _fmt_date(invoice.paid_at),
        "invoice_number": str(invoice.id)[:8].upper(),
    }

    try:
        from app.services.invoice_pdf_service import generate_invoice_pdf
        pdf_bytes = generate_invoice_pdf(invoice_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {e}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="fatura-{invoice_data["invoice_number"]}.pdf"'
        },
    )
