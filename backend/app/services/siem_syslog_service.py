"""F37.ext — CEF Syslog Forwarder: encaminha eventos do Eternity para qualquer SIEM via syslog."""
from __future__ import annotations

import asyncio
import socket
import ssl
import struct
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ── CEF Formatter ─────────────────────────────────────────────────────────────

CEF_VERSION = "CEF:0"
VENDOR = "Eternity"
PRODUCT = "SecOps"
VERSION = "1.0"

SEVERITY_MAP = {
    "info":     1,
    "low":      3,
    "medium":   5,
    "high":     7,
    "critical": 10,
}

FACILITY_USER = 1


def _cef_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("=", "\\=").replace("\n", " ")


def format_cef(
    event_type: str,
    severity: str,
    name: str,
    source_host: str = "-",
    dest_host: str = "-",
    message: str = "",
    extra: dict | None = None,
) -> str:
    sev_int = SEVERITY_MAP.get(severity.lower(), 5)
    extensions: list[str] = [
        f"src={_cef_escape(source_host)}",
        f"dst={_cef_escape(dest_host)}",
        f"msg={_cef_escape(message[:512])}",
    ]
    if extra:
        for k, v in extra.items():
            extensions.append(f"{_cef_escape(k)}={_cef_escape(str(v))}")

    ext_str = " ".join(extensions)
    signature_id = event_type.replace(" ", "_").upper()
    return (
        f"{CEF_VERSION}|{_cef_escape(VENDOR)}|{_cef_escape(PRODUCT)}|{VERSION}"
        f"|{_cef_escape(signature_id)}|{_cef_escape(name)}|{sev_int}|{ext_str}"
    )


def _rfc3164_header(facility: int, severity: int) -> str:
    pri = facility * 8 + min(severity, 7)
    now = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")
    return f"<{pri}>{now} eternity-secops "


def build_syslog_message(cef_line: str, facility: int = FACILITY_USER) -> bytes:
    header = _rfc3164_header(facility, 6)
    msg = header + cef_line + "\n"
    return msg.encode("utf-8")


# ── Sender ────────────────────────────────────────────────────────────────────

async def send_cef_event(
    target_host: str,
    target_port: int,
    protocol: str,
    tls_enabled: bool,
    tls_verify: bool,
    facility: int,
    event_type: str,
    severity: str,
    name: str,
    source_host: str = "-",
    message: str = "",
    extra: dict | None = None,
) -> None:
    cef_line = format_cef(event_type, severity, name, source_host, message=message, extra=extra)
    payload = build_syslog_message(cef_line, facility)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        _send_sync,
        target_host, target_port, protocol, tls_enabled, tls_verify, payload,
    )


def _send_sync(
    host: str,
    port: int,
    protocol: str,
    tls_enabled: bool,
    tls_verify: bool,
    payload: bytes,
) -> None:
    if protocol == "udp":
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        sock.sendto(payload, (host, port))
        sock.close()
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    if tls_enabled:
        ctx = ssl.create_default_context() if tls_verify else ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if not tls_verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        sock = ctx.wrap_socket(sock, server_hostname=host)
    sock.connect((host, port))
    # RFC 6587 framing: octet-count SP message
    framed = f"{len(payload)} ".encode() + payload
    sock.sendall(framed)
    sock.close()


# ── DB helpers ────────────────────────────────────────────────────────────────

async def list_syslog_configs(db: AsyncSession, tenant_id: UUID) -> list:
    from app.models.siem_syslog import SiemSyslogConfig
    result = await db.execute(
        select(SiemSyslogConfig)
        .where(SiemSyslogConfig.tenant_id == tenant_id)
        .order_by(SiemSyslogConfig.name)
    )
    return list(result.scalars().all())


async def forward_siem_alert(db: AsyncSession, tenant_id: UUID, alert) -> int:
    """Forward a SiemAlert to all active syslog configs of the tenant."""
    configs = await list_syslog_configs(db, tenant_id)
    forwarded = 0
    for cfg in configs:
        if not cfg.enabled:
            continue
        sev = alert.severity if hasattr(alert, "severity") else "medium"
        min_sev_rank = SEVERITY_MAP.get(cfg.min_severity, 0)
        alert_rank = SEVERITY_MAP.get(sev, 5)
        if alert_rank < min_sev_rank:
            continue
        try:
            await send_cef_event(
                target_host=cfg.target_host,
                target_port=cfg.target_port,
                protocol=cfg.protocol,
                tls_enabled=cfg.tls_enabled,
                tls_verify=cfg.tls_verify,
                facility=cfg.facility,
                event_type="SIEM_ALERT",
                severity=sev,
                name=alert.title if hasattr(alert, "title") else "Alert",
                source_host=alert.affected_host or "-" if hasattr(alert, "affected_host") else "-",
                message=alert.description or "" if hasattr(alert, "description") else "",
                extra={
                    "tenantId": str(tenant_id),
                    "sourceRuleId": alert.source_rule_id or "" if hasattr(alert, "source_rule_id") else "",
                    "sourceIp": alert.source_ip or "" if hasattr(alert, "source_ip") else "",
                },
            )
            cfg.events_forwarded = (cfg.events_forwarded or 0) + 1
            cfg.last_forward_at = datetime.now(timezone.utc)
            forwarded += 1
        except Exception:
            pass
    if forwarded:
        await db.flush()
    return forwarded
