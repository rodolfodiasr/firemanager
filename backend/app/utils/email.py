import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger()


def _smtp_settings() -> tuple[str, int, str, str, str]:
    """Return (host, port, user, password, email_from) from DB cache → env."""
    from app.services import platform_config_service
    host = platform_config_service.get_sync("smtp_host") or settings.smtp_host
    port = int(platform_config_service.get_sync("smtp_port") or settings.smtp_port)
    user = platform_config_service.get_sync("smtp_user") or settings.smtp_user
    password = platform_config_service.get_sync("smtp_password") or settings.smtp_password
    from_addr = platform_config_service.get_sync("email_from") or settings.email_from
    return host, port, user, password, from_addr


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

    smtp_host, smtp_port, smtp_user, smtp_password, email_from = _smtp_settings()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Convite para {tenant_name} — FireManager"
    msg["From"] = email_from
    msg["To"] = to_email
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
        log.info("Invite email sent", to=to_email, tenant=tenant_name)
    except Exception as exc:
        log.warning("Invite email failed", error=str(exc), to=to_email)


def _smtp_send(msg: MIMEMultipart, to_emails: list[str]) -> None:
    """Shared SMTP send helper."""
    smtp_host, smtp_port, smtp_user, smtp_password, _ = _smtp_settings()
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
        log.info("Email sent", to=to_emails)
    except Exception as exc:
        log.warning("Email send failed", error=str(exc), to=to_emails)


def send_score_alert_email(
    to_emails: list[str],
    tenant_name: str,
    scores: dict[str, Any],          # {"eternity": {"prev": 72.0, "new": 58.0}, ...}
    scan_summary: dict[str, Any],    # {"servers_scanned": 3, "devices_scanned": 2, "errors": 1}
    frontend_url: str = "http://localhost:5173",
) -> None:
    """Alert tenant admins when the Eternity Trust Score drops significantly or falls below 60."""
    _, _, smtp_user_val, _, _ = _smtp_settings()
    if not to_emails or not smtp_user_val:
        return

    eternity = scores.get("eternity", {})
    prev_e   = eternity.get("prev")
    new_e    = eternity.get("new", 0.0)
    drop     = round((prev_e - new_e), 1) if prev_e is not None else None

    subject_parts = []
    if drop is not None and drop >= 5:
        subject_parts.append(f"queda de {drop:.0f} pontos")
    if new_e < 60:
        subject_parts.append(f"score abaixo de 60 ({new_e:.0f})")
    subject_suffix = " — " + ", ".join(subject_parts) if subject_parts else ""
    subject = f"FireManager — Conformidade atualizada: {tenant_name}{subject_suffix}"

    def _score_color(v: float) -> str:
        if v >= 75: return "#38a169"
        if v >= 60: return "#d69e2e"
        return "#e53e3e"

    def _score_row(label: str, info: dict) -> str:
        p = info.get("prev")
        n = info.get("new", 0.0)
        arrow = ""
        if p is not None:
            diff = n - p
            if abs(diff) >= 0.5:
                arrow = (
                    f'<span style="color:#e53e3e;font-weight:600"> ▼ {abs(diff):.1f}</span>'
                    if diff < 0 else
                    f'<span style="color:#38a169;font-weight:600"> ▲ {diff:.1f}</span>'
                )
        return (
            f'<tr><td style="padding:6px 12px;color:#555">{label}</td>'
            f'<td style="padding:6px 12px;color:{_score_color(n)};font-weight:bold">{n:.1f}%</td>'
            f'<td style="padding:6px 12px">{f"{p:.1f}%" if p is not None else "—"}{arrow}</td></tr>'
        )

    score_rows = "".join([
        _score_row("Eternity Trust Score", scores.get("eternity", {})),
        _score_row("CIS Benchmark",        scores.get("cis", {})),
        _score_row("NIST CSF 2.0",         scores.get("nist", {})),
        _score_row("ISO 27001:2022",        scores.get("iso", {})),
    ])

    errors = scan_summary.get("errors", 0)
    error_note = (
        f'<p style="color:#c53030;font-size:13px">⚠ {errors} dispositivo(s)/servidor(es) com erro de coleta — verifique credenciais.</p>'
        if errors > 0 else ""
    )

    body_html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#1a1a1a">
  <div style="border-left:4px solid #e85d04;padding-left:16px;margin-bottom:20px">
    <h2 style="margin:0 0 4px;color:#e85d04;font-size:18px">FireManager — Relatório de Conformidade</h2>
    <p style="margin:0;color:#666;font-size:13px">Tenant: <strong>{tenant_name}</strong></p>
  </div>

  <p style="font-size:14px;color:#333">
    O agendamento automático concluiu a varredura de conformidade.
    Foram analisados <strong>{scan_summary.get("servers_scanned", 0)} servidor(es)</strong>
    e <strong>{scan_summary.get("devices_scanned", 0)} dispositivo(s) de rede</strong>.
  </p>

  {error_note}

  <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px">
    <thead>
      <tr style="background:#f5f5f5">
        <th style="text-align:left;padding:8px 12px;color:#555;font-size:12px;text-transform:uppercase">Framework</th>
        <th style="text-align:left;padding:8px 12px;color:#555;font-size:12px;text-transform:uppercase">Novo Score</th>
        <th style="text-align:left;padding:8px 12px;color:#555;font-size:12px;text-transform:uppercase">Anterior</th>
      </tr>
    </thead>
    <tbody>{score_rows}</tbody>
  </table>

  <a href="{frontend_url}/governance"
     style="display:inline-block;background:#e85d04;color:#fff;padding:10px 22px;
            border-radius:6px;text-decoration:none;font-weight:600;font-size:14px">
    Ver Governança
  </a>

  <p style="color:#aaa;font-size:11px;margin-top:24px;border-top:1px solid #eee;padding-top:12px">
    FireManager — Varredura automática diária. Para desabilitar notificações, contate o administrador.
  </p>
</body>
</html>"""

    _, _, _, _, email_from = _smtp_settings()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = email_from
    msg["To"]      = ", ".join(to_emails)
    msg.attach(MIMEText(body_html, "html"))
    _smtp_send(msg, to_emails)
