"""Fase 40-B: Monta o contexto de dados para o AI Assistant.

Define o que cada role pode ver e executa queries seguras (sem credenciais).
Combina RAG da base de conhecimento com queries diretas ao banco.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_tenant_role import TenantRole


async def build_context_for_query(
    db: AsyncSession,
    tenant_id: UUID,
    user_role: TenantRole,
    query: str,
) -> str:
    """Monta contexto formatado para injetar no system prompt do assistant."""
    parts: list[str] = []

    # 1. RAG — base de conhecimento (F19)
    try:
        from app.services.knowledge_service import semantic_search_documents
        kb = await semantic_search_documents(db, tenant_id, query, top_k=4)
        if kb and kb.strip():
            parts.append(f"## Base de Conhecimento\n{kb}")
    except Exception:
        pass

    # 2. RAG — snapshots BookStack (F19)
    try:
        from app.services.embedding_service import semantic_search
        bs = await semantic_search(db, tenant_id, query, top_k=3)
        if bs and bs.strip():
            parts.append(f"## Documentação de Dispositivos\n{bs}")
    except Exception:
        pass

    # 3. Lista de devices (sem credentials — apenas campos públicos)
    devices_ctx = await _query_devices_summary(db, tenant_id)
    if devices_ctx:
        parts.append(f"## Dispositivos Gerenciados\n{devices_ctx}")

    # 4. Operações recentes (últimas 15)
    ops_ctx = await _query_recent_operations(db, tenant_id)
    if ops_ctx:
        parts.append(f"## Operações Recentes\n{ops_ctx}")

    # 5. Compliance (apenas para analyst_n2+)
    if user_role not in (TenantRole.readonly, TenantRole.analyst_n1):
        compliance_ctx = await _query_compliance_summary(db, tenant_id)
        if compliance_ctx:
            parts.append(f"## Postura de Compliance\n{compliance_ctx}")

    return "\n\n---\n\n".join(parts)


async def _query_devices_summary(db: AsyncSession, tenant_id: UUID) -> str:
    from app.models.device import Device
    result = await db.execute(
        select(
            Device.name,
            Device.vendor,
            Device.host,
            Device.status,
            Device.category,
        )
        .where(Device.tenant_id == tenant_id)
        .order_by(Device.name)
        .limit(50)
    )
    rows = result.all()
    if not rows:
        return ""
    lines = ["| Nome | Vendor | Host | Categoria | Status |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r.name} | {r.vendor.value if hasattr(r.vendor, 'value') else r.vendor} | {r.host} | {r.category.value if hasattr(r.category, 'value') else r.category} | {r.status.value if hasattr(r.status, 'value') else r.status} |")
    return "\n".join(lines)


async def _query_recent_operations(db: AsyncSession, tenant_id: UUID) -> str:
    from app.models.operation import Operation, OperationStatus
    from app.models.device import Device
    result = await db.execute(
        select(
            Operation.natural_language_input,
            Operation.intent,
            Operation.status,
            Operation.created_at,
            Device.name,
        )
        .join(Device, Operation.device_id == Device.id)
        .where(Device.tenant_id == tenant_id)
        .order_by(desc(Operation.created_at))
        .limit(15)
    )
    rows = result.all()
    if not rows:
        return ""
    lines = ["| Pedido | Intenção | Status | Dispositivo | Data |", "|---|---|---|---|---|"]
    for r in rows:
        pedido = (r.natural_language_input or "")[:60].replace("|", "\\|")
        intent = r.intent or "—"
        status = r.status.value if hasattr(r.status, 'value') else str(r.status)
        device_name = r.name or "—"
        data = r.created_at.strftime("%d/%m %H:%M") if r.created_at else "—"
        lines.append(f"| {pedido} | {intent} | {status} | {device_name} | {data} |")
    return "\n".join(lines)


async def _query_compliance_summary(db: AsyncSession, tenant_id: UUID) -> str:
    try:
        from app.models.compliance import ComplianceResult
        from sqlalchemy import func as sqlfunc
        result = await db.execute(
            select(
                ComplianceResult.framework,
                sqlfunc.count().label("total"),
                sqlfunc.sum(
                    sqlfunc.cast(ComplianceResult.status == "pass", db.bind.dialect.name == "postgresql" and "int" or "integer")  # type: ignore
                ).label("passed"),
            )
            .where(ComplianceResult.tenant_id == tenant_id)
            .group_by(ComplianceResult.framework)
        )
        rows = result.all()
        if not rows:
            return ""
        lines = ["| Framework | Score |", "|---|---|"]
        for r in rows:
            total = r.total or 1
            passed = r.passed or 0
            score = int((passed / total) * 100)
            lines.append(f"| {r.framework} | {score}% |")
        return "\n".join(lines)
    except Exception:
        return ""
