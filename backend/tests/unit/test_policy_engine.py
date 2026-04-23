import pytest
from uuid import uuid4

from app.policy_engine.schemas import ActionPlan, ActionStep, IntentType, RuleSpecModel
from app.policy_engine.validator import ValidationError, validate_action_plan


def _make_plan(intent: IntentType, rule_spec: RuleSpecModel | None = None) -> ActionPlan:
    return ActionPlan(
        intent=intent,
        device_id=uuid4(),
        steps=[ActionStep(sequence=1, action="create_rule")],
        rule_spec=rule_spec,
    )


def test_valid_create_rule_plan():
    plan = _make_plan(
        IntentType.create_rule,
        RuleSpecModel(
            name="Allow-HTTPS",
            src_address="192.168.1.0/24",
            dst_address="10.0.0.1",
            service="HTTPS",
            action="accept",
            comment="Allow HTTPS from LAN",
        ),
    )
    warnings = validate_action_plan(plan)
    assert isinstance(warnings, list)


def test_create_rule_without_spec_raises():
    plan = _make_plan(IntentType.create_rule, rule_spec=None)
    with pytest.raises(ValidationError):
        validate_action_plan(plan)


def test_any_any_rule_produces_warning():
    plan = _make_plan(
        IntentType.create_rule,
        RuleSpecModel(
            name="test",
            src_address="any",
            dst_address="any",
            service="any",
            action="accept",
        ),
    )
    warnings = validate_action_plan(plan)
    assert any("any" in w.lower() for w in warnings)
