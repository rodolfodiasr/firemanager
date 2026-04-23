import ipaddress
import re

from app.policy_engine.schemas import ActionPlan, IntentType


class ValidationError(Exception):
    pass


_UNSAFE_SERVICES = {"any", "all", "*"}
_UNSAFE_ADDRESSES = {"any", "0.0.0.0/0", "::/0"}


def validate_action_plan(plan: ActionPlan) -> list[str]:
    """Returns list of warnings (non-blocking). Raises ValidationError for blocking issues."""
    warnings: list[str] = []

    if plan.intent in (IntentType.create_rule, IntentType.edit_rule):
        spec = plan.rule_spec
        if not spec:
            raise ValidationError("rule_spec is required for create_rule/edit_rule")

        if not spec.name or len(spec.name) < 2:
            raise ValidationError("Rule name must have at least 2 characters")

        if spec.src_address.lower() in _UNSAFE_ADDRESSES:
            warnings.append("Source address is 'any' — this may be overly permissive")

        if spec.dst_address.lower() in _UNSAFE_ADDRESSES:
            warnings.append("Destination address is 'any' — this may be overly permissive")

        if spec.service.lower() in _UNSAFE_SERVICES:
            warnings.append("Service is 'any/all' — consider restricting to specific ports")

        if not spec.comment:
            warnings.append("Rule has no comment — consider adding documentation")

    if plan.intent == IntentType.create_group:
        spec_g = plan.group_spec
        if not spec_g:
            raise ValidationError("group_spec is required for create_group")
        if not spec_g.members:
            raise ValidationError("Group must have at least one member")

    return warnings
