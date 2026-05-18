"""F35 — Celery tasks: avaliação periódica de playbooks e execução de actions."""
from __future__ import annotations

import json
import structlog
from celery import shared_task

log = structlog.get_logger()


@shared_task(name="soar.execute_playbook_actions", bind=True, max_retries=1)
def execute_playbook_actions(self, execution_id: str, actions_json: str) -> dict:
    """Executa as actions de um PlaybookExecution. Chamado após trigger match."""
    import asyncio

    async def _run() -> dict:
        from datetime import datetime, timezone
        from app.database import AsyncSessionLocal
        from app.models.playbook import PlaybookExecution

        actions: list[dict] = json.loads(actions_json)
        taken: list[dict] = []

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            from uuid import UUID

            result = await db.execute(
                select(PlaybookExecution).where(PlaybookExecution.id == UUID(execution_id))
            )
            execution = result.scalar_one_or_none()
            if not execution:
                return {"error": "PlaybookExecution não encontrado"}

            for action in actions:
                action_type = action.get("type", "")
                params = action.get("params", {})
                action_result = await _dispatch_action(
                    action_type, params, execution.trigger_context, db, execution.tenant_id
                )
                taken.append({"type": action_type, "result": action_result})

            execution.actions_taken = taken
            execution.status = "completed"
            execution.resolved_at = datetime.now(timezone.utc)
            await db.flush()
            await db.refresh(execution)
            await db.commit()

            log.info("playbook_execution.completed", execution_id=execution_id, actions=len(taken))
            return {"execution_id": execution_id, "actions": len(taken)}

    return asyncio.run(_run())


async def _dispatch_action(
    action_type: str,
    params: dict,
    context: dict,
    db,
    tenant_id,
) -> dict:
    """Despacha uma action do playbook."""
    from uuid import UUID

    # Substituir variáveis de contexto nos params
    resolved_params = {
        k: v.format(**context) if isinstance(v, str) else v
        for k, v in params.items()
    }

    if action_type == "notify_slack":
        try:
            from app.services.slack_notifier import send_slack_message
            # Buscar webhook configurado do tenant
            await send_slack_message(
                webhook_url=context.get("slack_webhook", ""),
                message=resolved_params.get("message", "Playbook acionado"),
            )
            return {"sent": True}
        except Exception as exc:
            return {"error": str(exc)}

    if action_type == "notify_email":
        try:
            from app.services.email_notifier import send_email
            await send_email(
                to=resolved_params.get("to", ""),
                subject="Eternity SecOps — Alerta de Playbook",
                body=resolved_params.get("message", "Playbook acionado"),
            )
            return {"sent": True}
        except Exception as exc:
            return {"error": str(exc)}

    if action_type == "escalate_to_n2":
        log.info("playbook.escalate_n2", context=context)
        return {"escalated": True}

    if action_type == "ad_disable_user":
        upn = context.get("upn") or context.get("username")
        if upn:
            log.info("playbook.ad_disable_user", upn=upn)
            return {"action": "ad_disable_user", "upn": upn, "queued": True}
        return {"error": "UPN não encontrado no contexto"}

    if action_type == "revoke_jit_access":
        log.info("playbook.revoke_jit", context=context)
        return {"action": "revoke_jit", "queued": True}

    if action_type == "run_snapshot":
        return {"action": "snapshot_queued"}

    if action_type == "create_ticket_jira":
        try:
            from app.services.jira_notifier import create_jira_issue
            await create_jira_issue(
                tenant_id=str(tenant_id),
                summary=resolved_params.get("summary", "Playbook acionado"),
                description=str(context),
                priority=resolved_params.get("priority", "Medium"),
            )
            return {"created": True}
        except Exception as exc:
            return {"error": str(exc)}

    if action_type == "create_remediation":
        try:
            from app.services.remediation_service import generate_plan_from_context
            request_text = resolved_params.get("request", "Auto-remediação via SOAR playbook")
            await generate_plan_from_context(
                db=db,
                tenant_id=tenant_id,
                request=request_text,
                origin_type="soar_playbook",
                origin_ref=resolved_params.get("origin_ref"),
            )
            await db.commit()
            return {"plan_created": True}
        except Exception as exc:
            return {"error": str(exc)}

    return {"action": action_type, "status": "not_implemented"}


@shared_task(name="soar.evaluate_scheduled_triggers", bind=True)
def evaluate_scheduled_triggers(self) -> dict:
    """Avalia triggers agendados (risk_score, device_unreachable). Celery beat a cada minuto."""
    import asyncio

    async def _run() -> dict:
        from app.database import AsyncSessionLocal
        from app.services.soar_service import evaluate_trigger
        from app.models.playbook import PlaybookRule
        from sqlalchemy import select

        total_executions = 0
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PlaybookRule.tenant_id).where(
                    PlaybookRule.enabled.is_(True),
                    PlaybookRule.trigger_type.in_(["risk_score_drop", "device_unreachable"]),
                ).distinct()
            )
            tenant_ids = [row[0] for row in result.all()]

            for tid in tenant_ids:
                execs = await evaluate_trigger(db, tid, "scheduled_check", {})
                total_executions += len(execs)

        return {"tenant_count": len(tenant_ids), "executions_started": total_executions}

    return asyncio.run(_run())
