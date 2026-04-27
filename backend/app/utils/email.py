import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from app.config import settings

log = structlog.get_logger()


def send_invite_email(
    to_email: str,
    tenant_name: str,
    token: str,
    inviter_name: str,
    frontend_url: str = "http://localhost:5173",
) -> None:
    accept_url = f"{frontend_url}/invite/{token}"

    body_html = f"""
<!DOCTYPE html>
<html>
<body style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #111;">Convite para o FireManager</h2>
  <p><strong>{inviter_name}</strong> convidou você para fazer parte do tenant
     <strong>{tenant_name}</strong> no FireManager.</p>
  <p>
    <a href="{accept_url}"
       style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;
              border-radius:6px;text-decoration:none;font-weight:600;">
      Aceitar convite
    </a>
  </p>
  <p style="color:#666;font-size:13px;">Este convite expira em 48 horas.</p>
  <p style="color:#999;font-size:12px;">
    Se o botão não funcionar, copie este link: {accept_url}
  </p>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Convite para {tenant_name} — FireManager"
    msg["From"] = settings.email_from
    msg["To"] = to_email
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        log.info("Invite email sent", to=to_email, tenant=tenant_name)
    except Exception as exc:
        log.warning("Invite email failed", error=str(exc), to=to_email)
