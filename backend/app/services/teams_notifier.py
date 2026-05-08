"""Microsoft Teams webhook notification (Incoming Webhook connector)."""
from __future__ import annotations

import httpx

SEVERITY_COLORS = {"info": "00FF00", "warning": "FFA500", "critical": "FF0000"}


async def send(config: dict, title: str, body: str, severity: str) -> bool:
    webhook_url = config["webhook_url"]
    color = SEVERITY_COLORS.get(severity, "FFA500")
    payload = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": color,
        "summary": title,
        "sections": [
            {
                "activityTitle": f"**[{severity.upper()}]** {title}",
                "activityText": body,
                "activitySubtitle": "FireManager SecOps",
            }
        ],
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(webhook_url, json=payload)
        return r.status_code in (200, 202)
