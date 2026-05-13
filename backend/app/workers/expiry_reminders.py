"""F39 — Celery beat: lembretes proativos de expiração de senha AD."""
from __future__ import annotations

import structlog
from celery import shared_task

log = structlog.get_logger()

_REMIND_DAYS = [14, 7, 1]


@shared_task(name="expiry_reminders.check_password_expiry", bind=True)
def check_password_expiry(self) -> dict:
    """Verifica senhas prestes a expirar e envia lembretes por email.
    Celery beat: diariamente às 08:00.
    """
    import asyncio

    async def _run() -> dict:
        from datetime import datetime, timedelta, timezone
        from app.database import AsyncSessionLocal
        from app.models.identity_governance import IdentityConnector
        from app.services import local_ad_service as ldap
        from app.utils.crypto import decrypt_credentials
        from sqlalchemy import select

        sent_total = 0
        now = datetime.now(timezone.utc)

        async with AsyncSessionLocal() as db:
            connectors_result = await db.execute(
                select(IdentityConnector).where(IdentityConnector.is_active.is_(True))
            )
            connectors = connectors_result.scalars().all()

            for conn in connectors:
                try:
                    config = decrypt_credentials(conn.config_encrypted)
                    users = await ldap.list_users(config)
                except Exception as exc:
                    log.warning("expiry_reminder.connector_error", connector=str(conn.id), error=str(exc))
                    continue

                for user in users:
                    if not user.get("is_enabled") or not user.get("email"):
                        continue

                    pwd_set_str = user.get("password_last_set") or user.get("last_logon_str")
                    if not pwd_set_str:
                        continue

                    try:
                        pwd_set = datetime.fromisoformat(pwd_set_str)
                        if pwd_set.tzinfo is None:
                            pwd_set = pwd_set.replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue

                    # AD default maxPwdAge = 90 days (configurável por GPO)
                    max_age_days = config.get("max_pwd_age_days", 90)
                    expires_at = pwd_set + timedelta(days=max_age_days)
                    days_left = (expires_at - now).days

                    if days_left in _REMIND_DAYS:
                        try:
                            from app.services.email_notifier import send_email
                            await send_email(
                                to=user["email"],
                                subject=f"Sua senha expira em {days_left} dia(s) — Eternity SecOps",
                                body=(
                                    f"Olá {user.get('display_name', user['email'])},\n\n"
                                    f"Sua senha de rede expirará em {days_left} dia(s) ({expires_at.strftime('%d/%m/%Y')}).\n\n"
                                    f"Redefina sua senha agora para evitar o bloqueio da conta.\n\n"
                                    f"Portal de autoatendimento: {config.get('self_service_url', 'entre em contato com o suporte')}"
                                ),
                            )
                            sent_total += 1
                        except Exception as exc:
                            log.warning("expiry_reminder.email_error", user=user.get("email"), error=str(exc))

        log.info("expiry_reminders.done", sent=sent_total)
        return {"sent": sent_total}

    return asyncio.get_event_loop().run_until_complete(_run())
