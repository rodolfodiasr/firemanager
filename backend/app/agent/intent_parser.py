import json
from pathlib import Path
from typing import Any

import anthropic

from app.config import settings

_INTENT_PROMPT = (Path(__file__).parent / "prompts" / "intent.txt").read_text()
_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.txt").read_text()


class IntentParseResult:
    def __init__(self, data: dict[str, Any]) -> None:
        self.intent: str = data.get("intent", "unknown")
        self.present_fields: list[str] = data.get("present_fields", [])
        self.missing_fields: list[str] = data.get("missing_fields", [])
        self.extracted_data: dict[str, Any] = data.get("extracted_data", {})


async def parse_intent(user_input: str) -> IntentParseResult:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    prompt = _INTENT_PROMPT.replace("{user_input}", user_input)

    message = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    content = message.content[0].text if message.content else "{}"

    # Strip possible markdown fences
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
