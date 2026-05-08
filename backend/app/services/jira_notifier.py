"""Jira Cloud REST API — create issue on alert."""
from __future__ import annotations

import httpx
from base64 import b64encode

PRIORITY_MAP = {"info": "Low", "warning": "Medium", "critical": "High"}


async def create_issue(config: dict, title: str, body: str, severity: str) -> str | None:
    base = config["url"].rstrip("/")
    email = config["email"]
    api_token = config["api_token"]
    project_key = config["project_key"]
    issue_type = config.get("issue_type", "Task")

    auth = b64encode(f"{email}:{api_token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    priority = PRIORITY_MAP.get(severity, "Medium")
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": f"[FireManager][{severity.upper()}] {title}",
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}],
            },
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
        }
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{base}/rest/api/3/issue", json=payload, headers=headers)
        r.raise_for_status()
        return r.json().get("key")
