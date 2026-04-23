from app.connectors.base import GroupSpec, RuleSpec
from app.models.device import Device, VendorEnum
from app.policy_engine.schemas import ActionPlan, IntentType


def translate_to_connector_spec(plan: ActionPlan, device: Device) -> tuple[RuleSpec | None, GroupSpec | None]:
    """Convert ActionPlan into vendor-agnostic RuleSpec/GroupSpec for the connector layer."""
    rule_spec = None
    group_spec = None

    if plan.intent in (IntentType.create_rule, IntentType.edit_rule) and plan.rule_spec:
        r = plan.rule_spec
        rule_spec = RuleSpec(
            name=r.name,
            src_address=r.src_address,
            dst_address=r.dst_address,
            service=r.service,
            action=r.action,
            comment=r.comment,
            extra=r.extra,
        )

    if plan.intent == IntentType.create_group and plan.group_spec:
        g = plan.group_spec
        group_spec = GroupSpec(name=g.name, members=g.members, comment=g.comment)

    return rule_spec, group_spec
