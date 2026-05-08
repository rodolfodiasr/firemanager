"""Generic HTTP webhook notification."""
from __future__ import annotations

import httpx


async def send(config: dict, title: str, body: str, severity: str) -> bool:
    url = config["url"]
    method = config.get("method", "POST").upper()
    headers = config.get("headers", {})
    payload = {
        "title": title,
        "body": body,
        "severity": severity,
        "source": "firemanager",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        if method == "POST":
            r = await client.post(url, json=payload, headers=headers)
        else:
            r = await client.get(url, params=payload, headers=headers)
        return r.status_code < 400
