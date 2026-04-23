import json
from pathlib import Path
from typing import Any
from uuid import UUID

import anthropic

from app.config import settings
from app.policy_engine.schemas import ActionPlan

_PLAN_PROMPT = (Path(__file__).parent / "prompts" / "plan.txt").read_text()
_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.txt").read_text()


async def generate_action_plan(
    device_id: UUID,
    vendor: str,
    firmware_version: str | None,
    intent: str,
    collected_data: dict[str, Any],
) -> ActionPlan:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    prompt = (
        _PLAN_PROMPT
        .replace("{device_id}", str(device_id))
        .replace("{vendor}", vendor)
        .replace("{firmware_version}", firmware_version or "unknown")
        .replace("{intent}", intent)
        .replace("{collected_data}", json.dumps(collected_data, ensure_ascii=False, indent=2))
    )

    message = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.anthropic_max_tokens,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    content = message.content[0].text if message.content else "{}"
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.rsplit("```", 1)[0]

    data = json.loads(content)
    # Ensure device_id is a UUID object
    data["device_id"] = str(device_id)
    return ActionPlan.model_validate(data)
