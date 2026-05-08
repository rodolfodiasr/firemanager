"""SMTP email notification."""
from __future__ import annotations

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _send_sync(config: dict, title: str, body: str, severity: str) -> bool:
    host = config["host"]
    port = int(config.get("port", 587))
    username = config["username"]
    password = config["password"]
    from_addr = config.get("from_address", username)
    to_addrs = config.get("to_addresses", [])
    if isinstance(to_addrs, str):
        to_addrs = [to_addrs]
    use_tls = config.get("use_tls", True)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[FireManager][{severity.upper()}] {title}"
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    html = f"<h3>[{severity.upper()}] {title}</h3><p>{body}</p><hr><small>FireManager SecOps</small>"
    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(html, "html"))

    if use_tls:
        server = smtplib.SMTP(host, port)
        server.starttls()
    else:
        server = smtplib.SMTP_SSL(host, port)
    server.login(username, password)
    server.sendmail(from_addr, to_addrs, msg.as_string())
    server.quit()
    return True


async def send(config: dict, title: str, body: str, severity: str) -> bool:
    return await asyncio.to_thread(_send_sync, config, title, body, severity)
