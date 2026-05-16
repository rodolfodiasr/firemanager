from __future__ import annotations
import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.web_audit import WebAuditConfig, WebAuditEntry, WebAuditFinding


RISK_CATEGORIES = {"malicious", "suspicious", "shadow_it"}


async def get_or_create_config(db: AsyncSession, tenant_id: UUID) -> WebAuditConfig:
    result = await db.execute(select(WebAuditConfig).where(WebAuditConfig.tenant_id == tenant_id))
    cfg = result.scalar_one_or_none()
    if not cfg:
        cfg = WebAuditConfig(tenant_id=tenant_id)
        db.add(cfg)
        await db.flush()
        await db.refresh(cfg)
    return cfg


def extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.netloc or url[:100]
    except Exception:
        return url[:100]


def parse_browsing_history_csv(content: str) -> list[dict]:
    """
    Parseia export do BrowsingHistoryView.
    Suporta separadores , e \\t. Colunas esperadas (case-insensitive):
    URL, Title, Visit Count, Visited On, Browser, Web Site / Domain
    """
    rows = []
    # Detectar separador
    sep = "\t" if "\t" in content.split("\n")[0] else ","
    reader = csv.DictReader(io.StringIO(content), delimiter=sep)
    for row in reader:
        # Normalizar chaves
        normalized = {k.strip().lower(): v.strip() for k, v in row.items() if k}
        url = normalized.get("url", "")
        if not url:
            continue

        # Parse data
        visited_raw = normalized.get("visited on", normalized.get("visited_on", ""))
        try:
            visited_at = datetime.fromisoformat(visited_raw.replace("Z", "+00:00"))
        except Exception:
            visited_at = datetime.now(timezone.utc)

        rows.append({
            "url": url,
            "domain": extract_domain(url),
            "title": normalized.get("title", ""),
            "visit_count": int(normalized.get("visit count", normalized.get("visit_count", "1")) or "1"),
            "visited_at": visited_at,
            "browser": normalized.get("browser", ""),
        })
    return rows


async def ingest_entries(
    db: AsyncSession,
    tenant_id: UUID,
    config_id: UUID,
    rows: list[dict],
    workstation: str,
    ad_user: Optional[str] = None,
    department: Optional[str] = None,
) -> int:
    count = 0
    for row in rows:
        entry = WebAuditEntry(
            tenant_id=tenant_id,
            config_id=config_id,
            workstation=workstation,
            ad_user=ad_user,
            department=department,
            url=row["url"],
            domain=row["domain"],
            visited_at=row["visited_at"],
            browser=row.get("browser"),
            title=row.get("title"),
            visit_count=row.get("visit_count", 1),
        )
        db.add(entry)
        count += 1
    await db.flush()
    return count


async def analyze_entries_with_ai(db: AsyncSession, tenant_id: UUID, limit: int = 100) -> int:
    """Classifica entradas não analisadas com Claude Haiku."""
    from app.config import settings
    import anthropic

    result = await db.execute(
        select(WebAuditEntry)
        .where(WebAuditEntry.tenant_id == tenant_id, WebAuditEntry.ai_analyzed == False)  # noqa: E712
        .limit(limit)
    )
    entries = list(result.scalars().all())
    if not entries:
        return 0

    # Agrupar domínios únicos
    domains = list({e.domain for e in entries})
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Processar em lotes de 30 domínios
    domain_categories: dict[str, dict] = {}
    batch_size = 30
    for i in range(0, len(domains), batch_size):
        batch = domains[i:i + batch_size]
        prompt = (
            "Classifique cada domínio abaixo em uma dessas categorias:\n"
            "- productivity: ferramentas de trabalho (Office365, GitHub, Jira, Slack, etc.)\n"
            "- social: redes sociais (Facebook, Instagram, Twitter/X, TikTok, LinkedIn pessoal)\n"
            "- streaming: entretenimento (YouTube, Netflix, Spotify, Twitch)\n"
            "- shadow_it: cloud não aprovado (Dropbox pessoal, WeTransfer, SendAnywhere)\n"
            "- malicious: phishing, malware, C2, domínios suspeitos conhecidos\n"
            "- suspicious: proxies, VPNs gratuitas, anonimizadores\n"
            "- unknown: não classificado\n\n"
            f"Domínios:\n{chr(10).join(batch)}\n\n"
            'Responda SOMENTE com JSON válido: [{"domain": "...", "category": "...", "risk_note": "..."}]'
        )
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            text_resp = msg.content[0].text.strip()
            # Extrair JSON
            match = re.search(r"\[.*\]", text_resp, re.DOTALL)
            if match:
                classifications = json.loads(match.group())
                for item in classifications:
                    domain_categories[item["domain"]] = {
                        "category": item.get("category", "unknown"),
                        "risk_note": item.get("risk_note", ""),
                    }
        except Exception:
            pass

    analyzed = 0
    for entry in entries:
        info = domain_categories.get(entry.domain, {})
        category = info.get("category", "unknown")
        entry.category = category
        entry.ai_analyzed = True
        analyzed += 1

        # Criar finding se categoria de risco
        if category in RISK_CATEGORIES:
            severity = "critical" if category == "malicious" else "high" if category == "suspicious" else "medium"
            finding_type = (
                "malicious_site" if category == "malicious"
                else "shadow_it" if category == "shadow_it"
                else "policy_violation"
            )
            finding = WebAuditFinding(
                tenant_id=tenant_id,
                entry_id=entry.id,
                workstation=entry.workstation,
                ad_user=entry.ad_user,
                department=entry.department,
                finding_type=finding_type,
                severity=severity,
                domain=entry.domain,
                description=info.get("risk_note") or f"Domínio classificado como {category}: {entry.domain}",
                recommendation="Bloquear domínio no firewall e investigar o usuário." if category == "malicious" else "Revisar política de uso aceitável.",
                ai_confidence=0.85,
            )
            db.add(finding)

    await db.flush()
    return analyzed


async def get_user_risk_summary(db: AsyncSession, tenant_id: UUID, days: int = 30) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            WebAuditEntry.ad_user,
            WebAuditEntry.department,
            func.count().label("total_visits"),
            func.sum(
                text("CASE WHEN category = 'malicious' THEN 1 ELSE 0 END")
            ).label("malicious_count"),
            func.sum(
                text("CASE WHEN category = 'shadow_it' THEN 1 ELSE 0 END")
            ).label("shadow_it_count"),
        )
        .where(WebAuditEntry.tenant_id == tenant_id, WebAuditEntry.visited_at >= since)
        .group_by(WebAuditEntry.ad_user, WebAuditEntry.department)
        .order_by(text("malicious_count DESC, shadow_it_count DESC"))
        .limit(50)
    )
    rows = result.all()
    summaries = []
    for r in rows:
        mal = int(r.malicious_count or 0)
        shadow = int(r.shadow_it_count or 0)
        total = int(r.total_visits or 1)
        risk_score = (mal * 10 + shadow * 3) / max(total, 1) * 100
        risk_level = "critical" if mal > 0 else "high" if shadow > 5 else "medium" if shadow > 0 else "low"
        productivity = max(0, min(100, 100 - int(risk_score)))
        summaries.append({
            "ad_user": r.ad_user or "desconhecido",
            "department": r.department,
            "total_visits": total,
            "malicious_count": mal,
            "shadow_it_count": shadow,
            "productivity_score": productivity,
            "risk_level": risk_level,
        })
    return summaries


async def get_domain_stats(db: AsyncSession, tenant_id: UUID, days: int = 30, limit: int = 50) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            WebAuditEntry.domain,
            WebAuditEntry.category,
            func.count().label("visit_count"),
            func.count(func.distinct(WebAuditEntry.ad_user)).label("unique_users"),
        )
        .where(WebAuditEntry.tenant_id == tenant_id, WebAuditEntry.visited_at >= since)
        .group_by(WebAuditEntry.domain, WebAuditEntry.category)
        .order_by(text("visit_count DESC"))
        .limit(limit)
    )
    return [
        {"domain": r.domain, "category": r.category or "unknown",
         "visit_count": r.visit_count, "unique_users": r.unique_users}
        for r in result.all()
    ]


async def get_findings(
    db: AsyncSession,
    tenant_id: UUID,
    severity: Optional[str] = None,
    finding_type: Optional[str] = None,
    limit: int = 200,
) -> list[WebAuditFinding]:
    q = select(WebAuditFinding).where(WebAuditFinding.tenant_id == tenant_id)
    if severity:
        q = q.where(WebAuditFinding.severity == severity)
    if finding_type:
        q = q.where(WebAuditFinding.finding_type == finding_type)
    q = q.order_by(WebAuditFinding.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())
