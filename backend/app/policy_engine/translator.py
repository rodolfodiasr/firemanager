from app.connectors.base import GroupSpec, NatSpec, RouteSpec, RuleSpec
from app.models.device import Device, VendorEnum
from app.policy_engine.schemas import ActionPlan, IntentType


def translate_to_connector_spec(
    plan: ActionPlan, device: Device
) -> tuple[RuleSpec | None, GroupSpec | None, NatSpec | None, RouteSpec | None]:
    """Convert ActionPlan into vendor-agnostic specs for the connector layer."""
    rule_spec = None
    group_spec = None
    nat_spec = None
    route_spec = None

    if plan.intent in (IntentType.create_rule, IntentType.edit_rule) and plan.rule_spec:
        r = plan.rule_spec
        rule_spec = RuleSpec(
            name=r.name,
            src_address=r.src_address,
            dst_address=r.dst_address,
            src_zone=r.src_zone,
            dst_zone=r.dst_zone,
            service=r.service,
            action=r.action,
            comment=r.comment,
            extra=r.extra,
        )

    if plan.intent == IntentType.create_group and plan.group_spec:
        g = plan.group_spec
        group_spec = GroupSpec(name=g.name, members=g.members, comment=g.comment)

    if plan.intent == IntentType.create_nat_policy and plan.nat_spec:
        n = plan.nat_spec
        nat_spec = NatSpec(
            name=n.name,
            inbound_interface=n.inbound_interface,
            outbound_interface=n.outbound_interface,
            source=n.source,
            translated_source=n.translated_source,
            destination=n.destination,
            translated_destination=n.translated_destination,
            service=n.service,
            translated_service=n.translated_service,
            comment=n.comment,
            enable=n.enable,
        )

    if plan.intent == IntentType.create_route_policy and plan.route_spec:
        rs = plan.route_spec
        route_spec = RouteSpec(
            interface=rs.interface,
            destination=rs.destination,
            source=rs.source,
            service=rs.service,
            gateway=rs.gateway,
            metric=rs.metric,
            distance=rs.distance,
            name=rs.name,
            route_type=rs.route_type,
            comment=rs.comment,
            disable_on_interface_down=rs.disable_on_interface_down,
        )

    return rule_spec, group_spec, nat_spec, route_spec
