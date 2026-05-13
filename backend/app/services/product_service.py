import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import (
    BillingInvoice, BillingPlan, BillingSubscription,
    HelpArticle, OnboardingChecklist, UserPreference,
)

_DEFAULT_PLANS = [
    {
        "name": "Starter",
        "slug": "starter",
        "monthly_price_brl": Decimal("490.00"),
        "max_devices": 10,
        "max_users": 5,
        "ai_token_quota": 100_000,
        "sla_target_pct": Decimal("99.0"),
        "features": {"alerts": True, "compliance": False, "siem": False, "edge_agent": False},
    },
    {
        "name": "Pro",
        "slug": "pro",
        "monthly_price_brl": Decimal("1490.00"),
        "max_devices": 50,
        "max_users": 20,
        "ai_token_quota": 1_000_000,
        "sla_target_pct": Decimal("99.5"),
        "features": {"alerts": True, "compliance": True, "siem": True, "edge_agent": False},
    },
    {
        "name": "Enterprise",
        "slug": "enterprise",
        "monthly_price_brl": Decimal("3490.00"),
        "max_devices": None,
        "max_users": None,
        "ai_token_quota": None,
        "sla_target_pct": Decimal("99.9"),
        "features": {"alerts": True, "compliance": True, "siem": True, "edge_agent": True},
    },
]

_BUILTIN_ARTICLES = [
    {
        "title": "Como adicionar seu primeiro dispositivo",
        "slug": "primeiro-dispositivo",
        "category": "getting-started",
        "persona": "admin",
        "content_md": "# Como adicionar um dispositivo\n\nAcesse **Firewalls > Dispositivos** e clique em **Novo Dispositivo**...",
        "is_published": True,
        "sort_order": 1,
    },
    {
        "title": "Fazendo sua primeira pergunta ao Agente IA",
        "slug": "primeira-pergunta-agente",
        "category": "getting-started",
        "persona": "analyst",
        "content_md": "# Usando o Agente IA\n\nO Agente IA entende comandos em linguagem natural...",
        "is_published": True,
        "sort_order": 2,
    },
    {
        "title": "Configurando alertas por Slack",
        "slug": "alertas-slack",
        "category": "integration",
        "persona": "admin",
        "content_md": "# Alertas via Slack\n\nAcesse **Segurança > Alertas** e configure um canal...",
        "is_published": True,
        "sort_order": 3,
    },
    {
        "title": "Entendendo o Dashboard Executivo",
        "slug": "dashboard-executivo",
        "category": "reports",
        "persona": "admin",
        "content_md": "# Dashboard Executivo\n\nO score de risco 0–100 é calculado com base em...",
        "is_published": True,
        "sort_order": 4,
    },
]


async def seed_plans(db: AsyncSession) -> list[BillingPlan]:
    created = []
    for p in _DEFAULT_PLANS:
        existing = await db.scalar(select(BillingPlan).where(BillingPlan.slug == p["slug"]))
        if existing:
            continue
        plan = BillingPlan(**p)
        db.add(plan)
        created.append(plan)
    await db.flush()
    for p in created:
        await db.refresh(p)
    return created


async def seed_articles(db: AsyncSession, created_by: Optional[uuid.UUID] = None) -> list[HelpArticle]:
    created = []
    for a in _BUILTIN_ARTICLES:
        existing = await db.scalar(select(HelpArticle).where(HelpArticle.slug == a["slug"]))
        if existing:
            continue
        article = HelpArticle(created_by=created_by, **a)
        db.add(article)
        created.append(article)
    await db.flush()
    for a in created:
        await db.refresh(a)
    return created


async def get_or_create_checklist(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> OnboardingChecklist:
    existing = await db.scalar(
        select(OnboardingChecklist).where(
            OnboardingChecklist.tenant_id == tenant_id,
            OnboardingChecklist.user_id == user_id,
        )
    )
    if existing:
        return existing
    checklist = OnboardingChecklist(tenant_id=tenant_id, user_id=user_id)
    db.add(checklist)
    await db.flush()
    await db.refresh(checklist)
    return checklist


async def complete_step(
    db: AsyncSession,
    checklist: OnboardingChecklist,
    step: str,
) -> OnboardingChecklist:
    setattr(checklist, f"step_{step}", True)
    all_done = (
        checklist.step_add_device
        and checklist.step_run_snapshot
        and checklist.step_ask_agent
        and checklist.step_configure_alert
    )
    if all_done and not checklist.completed:
        checklist.completed = True
        checklist.completed_at = datetime.utcnow()
    await db.flush()
    await db.refresh(checklist)
    return checklist


async def get_or_create_preferences(db: AsyncSession, user_id: uuid.UUID) -> UserPreference:
    existing = await db.scalar(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    if existing:
        return existing
    prefs = UserPreference(user_id=user_id)
    db.add(prefs)
    await db.flush()
    await db.refresh(prefs)
    return prefs


async def create_subscription(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    plan_slug: str = "starter",
) -> BillingSubscription:
    existing = await db.scalar(
        select(BillingSubscription).where(BillingSubscription.tenant_id == tenant_id)
    )
    if existing:
        return existing
    plan = await db.scalar(select(BillingPlan).where(BillingPlan.slug == plan_slug))
    if not plan:
        raise ValueError(f"Plan '{plan_slug}' not found — run seed first")
    sub = BillingSubscription(tenant_id=tenant_id, plan_id=plan.id, status="active")
    db.add(sub)
    await db.flush()
    await db.refresh(sub)
    return sub
