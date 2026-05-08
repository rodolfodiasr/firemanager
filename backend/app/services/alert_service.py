"""Fase 23 — Alert dispatch engine."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertChannel, AlertRule, AlertEvent, AlertChannelType
from app.utils.crypto import decrypt_credentials


async def fire_alert(
    db: AsyncSession,
    tenant_id,
    trigger: str,
    title: str,
    body: str,
    severity: str = "warning",
) -> None:
    """Find matching rules for this trigger and dispatch to all configured channels."""
    rules = (await db.execute(
        select(AlertRule).where(
            AlertRule.tenant_id == tenant_id,
            AlertRule.trigger == trigger,
            AlertRule.is_active.is_(True),
        )
    )).scalars().all()

    for rule in rules:
        channels_result: dict[str, str] = {}
        channel_ids = rule.channel_ids or []

        dispatch_tasks = []
        for ch_id in channel_ids:
            ch = await db.get(AlertChannel, UUID(ch_id))
            if ch and ch.is_active:
                dispatch_tasks.append(_dispatch_channel(ch, title, body, severity))

        results = await asyncio.gather(*dispatch_tasks, return_exceptions=True)
        for ch_id, result in zip(channel_ids, results):
            channels_result[ch_id] = "success" if result is True else str(result)

        event = AlertEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            rule_id=rule.id,
            trigger=trigger,
            severity=severity,
            title=title,
            body=body,
            channels_result=channels_result,
        )
        db.add(event)

    await db.flush()


async def _dispatch_channel(channel: AlertChannel, title: str, body: str, severity: str) -> bool:
    try:
        config = decrypt_credentials(channel.encrypted_config)
        ch_type = channel.channel_type

        if ch_type == AlertChannelType.slack:
            from app.services.slack_notifier import send
            return await send(config, title, body, severity)
        elif ch_type == AlertChannelType.teams:
            from app.services.teams_notifier import send
            return await send(config, title, body, severity)
        elif ch_type == AlertChannelType.email:
            from app.services.email_notifier import send
            return await send(config, title, body, severity)
        elif ch_type == AlertChannelType.webhook:
            from app.services.webhook_notifier import send
            return await send(config, title, body, severity)
        elif ch_type == AlertChannelType.jira:
            from app.services.jira_notifier import create_issue
            issue_key = await create_issue(config, title, body, severity)
            return issue_key is not None
        return False
    except Exception:
        return False


async def test_channel(channel: AlertChannel) -> tuple[bool, str]:
    try:
        ok = await _dispatch_channel(channel, "Teste de Canal", "Este é um teste de integração do FireManager.", "info")
        return ok, "Mensagem enviada com sucesso" if ok else "Falha ao enviar mensagem"
    except Exception as e:
        return False, str(e)
