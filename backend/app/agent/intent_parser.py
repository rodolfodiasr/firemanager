import json
from pathlib import Path
from typing import Any
from uuid import UUID

import anthropic

from app.config import settings

_INTENT_PROMPT = (Path(__file__).parent / "prompts" / "intent.txt").read_text()
_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.txt").read_text()
_FALLBACK_MODEL = "claude-haiku-4-5-20251001"


class IntentParseResult:
    def __init__(self, data: dict[str, Any]) -> None:
        self.intent: str = data.get("intent", "unknown")
        self.present_fields: list[str] = data.get("present_fields", [])
        self.missing_fields: list[str] = data.get("missing_fields", [])
        self.extracted_data: dict[str, Any] = data.get("extracted_data", {})


async def parse_intent(
    user_input: str,
    tenant_id: UUID | None = None,
    db: Any = None,
) -> IntentParseResult:
    prompt = _INTENT_PROMPT.replace("{user_input}", user_input)

    # Use per-tenant LLM provider when db + tenant_id are available
    if db is not None and tenant_id is not None:
        try:
            from app.services.llm_config_service import resolve_provider
            provider = await resolve_provider(tenant_id, db)
            content, _, _ = await provider.chat(
                messages=[{"role": "user", "content": prompt}],
                system=_SYSTEM_PROMPT,
                max_tokens=1024,
            )
        except Exception:
            content = await _call_anthropic(prompt)
    else:
        content = await _call_anthropic(prompt)

    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {"intent": "unknown", "present_fields": [], "missing_fields": [], "extracted_data": {}}

    return IntentParseResult(data)


async def _call_anthropic(prompt: str) -> str:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    primary = settings.anthropic_model
    try:
        message = await client.messages.create(
            model=primary,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.InternalServerError as exc:
        if exc.status_code == 529 and primary != _FALLBACK_MODEL:
            message = await client.messages.create(
                model=_FALLBACK_MODEL,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
        else:
            raise

    return message.content[0].text if message.content else "{}"
