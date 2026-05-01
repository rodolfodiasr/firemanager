import json
from pathlib import Path
from typing import Any
from uuid import UUID

import anthropic

from app.config import settings
from app.policy_engine.schemas import ActionPlan

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_PLAN_BASE = (_PROMPTS_DIR / "plan_base.txt").read_text(encoding="utf-8")
_SYSTEM_PROMPT = (_PROMPTS_DIR / "system.txt").read_text(encoding="utf-8")
_VENDORS_DIR = _PROMPTS_DIR / "vendors"

_vendor_cache: dict[str, str] = {}


def _vendor_prompt(vendor: str) -> str:
    if vendor not in _vendor_cache:
        path = _VENDORS_DIR / f"{vendor}.txt"
        _vendor_cache[vendor] = path.read_text(encoding="utf-8") if path.exists() else ""
    return _vendor_cache[vendor]


async def generate_action_plan(
    device_id: UUID,
    vendor: str,
    firmware_version: str | None,
    intent: str,
    collected_data: dict[str, Any],
) -> ActionPlan:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    vendor_section = _vendor_prompt(vendor)
    full_template = _PLAN_BASE + ("\n\n" + vendor_section if vendor_section else "")

    prompt = (
        full_template
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
    data["device_id"] = str(device_id)
    return ActionPlan.model_validate(data)
