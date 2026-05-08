"""Slack webhook notification."""
from __future__ import annotations

import httpx

SEVERITY_COLORS = {"info": "#36a64f", "warning": "#ff9900", "critical": "#ff0000"}


async def send(config: dict, title: str, body: str, severity: str) -> bool:
    webhook_url = config["webhook_url"]
    color = SEVERITY_COLORS.get(severity, "#36a64f")
    payload = {
        "attachments": [
            {
                "color": color,
                "title": f"[{severity.upper()}] {title}",
                "text": body,
                "footer": "FireManager SecOps",
                "ts": __import__("time").time(),
            }
        ]
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(webhook_url, json=payload)
        return r.status_code == 200
