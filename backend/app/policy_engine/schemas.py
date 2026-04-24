from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    create_rule = "create_rule"
    delete_rule = "delete_rule"
    edit_rule = "edit_rule"
    create_group = "create_group"
    list_rules = "list_rules"
    health_check = "health_check"
    get_snapshot = "get_snapshot"
    unknown = "unknown"


class RuleSpecModel(BaseModel):
    name: str
    src_address: str
    dst_address: str
    src_zone: str = "LAN"
    dst_zone: str = "WAN"
    service: str
    action: str = "accept"
    comment: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class GroupSpecModel(BaseModel):
    name: str
    members: list[str]
    comment: str | None = None


class ActionStep(BaseModel):
    sequence: int
    action: str
    params: dict[str, Any] = Field(default_factory=dict)


class ActionPlan(BaseModel):
    intent: IntentType
    device_id: UUID
    steps: list[ActionStep]
    rule_spec: RuleSpecModel | None = None
    group_spec: GroupSpecModel | None = None
    raw_intent_data: dict[str, Any] = Field(default_factory=dict)
