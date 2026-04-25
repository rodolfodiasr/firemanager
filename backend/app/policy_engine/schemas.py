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
    list_nat_policies = "list_nat_policies"
    create_nat_policy = "create_nat_policy"
    delete_nat_policy = "delete_nat_policy"
    list_route_policies = "list_route_policies"
    create_route_policy = "create_route_policy"
    delete_route_policy = "delete_route_policy"
    configure_content_filter = "configure_content_filter"
    toggle_gateway_av = "toggle_gateway_av"
    toggle_anti_spyware = "toggle_anti_spyware"
    toggle_ips = "toggle_ips"
    toggle_app_control = "toggle_app_control"
    toggle_geo_ip = "toggle_geo_ip"
    toggle_botnet = "toggle_botnet"
    toggle_dpi_ssl = "toggle_dpi_ssl"
    configure_app_rules = "configure_app_rules"
    add_security_exclusion = "add_security_exclusion"
    get_security_status = "get_security_status"
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


class NatSpecModel(BaseModel):
    name: str
    inbound_interface: str = "X1"
    outbound_interface: str = "X1"
    source: str = "Any"
    translated_source: str = "Original"
    destination: str = "Any"
    translated_destination: str = "Original"
    service: str = "Any"
    translated_service: str = "Original"
    comment: str | None = None
    enable: bool = True


class RouteSpecModel(BaseModel):
    interface: str
    destination: str = "Any"
    source: str = "Any"
    service: str = "Any"
    gateway: str = "default"
    metric: int = 20
    distance: int = 20
    name: str = ""
    route_type: str = "standard"
    comment: str | None = None
    disable_on_interface_down: bool = False


class ContentFilterSpecModel(BaseModel):
    profile_name: str
    policy_name: str = ""
    blocked_categories: list[str] = Field(default_factory=list)
    allowed_categories: list[str] = Field(default_factory=list)
    zones: list[str] = Field(default_factory=lambda: ["LAN"])
    action: str = "block"
    comment: str | None = None


class GroupSpecModel(BaseModel):
    name: str
    members: list[str]
    comment: str | None = None


class SecurityServiceSpec(BaseModel):
    service: str  # gateway-antivirus | anti-spyware | intrusion-prevention | app-control | geo-ip | botnet | dpi-ssl-client | dpi-ssl-server
    enabled: bool = True
    # app-control: category IDs to block/unblock
    category_ids: list[int] = Field(default_factory=list)
    category_block: bool = True
    # geo-ip: countries to block/unblock
    countries: list[str] = Field(default_factory=list)
    country_action: str = "block"  # "block" | "unblock"


class SecurityExclusionSpec(BaseModel):
    group: str  # GRP-EXCLUSION-GEO-IP | GRP-EXCLUSION-BOOTNET | GRP-EXCLUSION-CFS
    ip_addresses: list[str]
    zone: str = "LAN"


class AppRulesSpec(BaseModel):
    policy_name: str
    enabled: bool = True
    source_address: str = "any"
    destination_address: str = "any"
    match_object_name: str = ""
    match_type: str = "application-list"  # "application-list" | "application-category-list"
    match_ids: list[int] = Field(default_factory=list)
    action_object: str = "Reset/Drop"
    zone: str = "LAN"
    comment: str | None = None


class ActionStep(BaseModel):
    sequence: int
    action: str
    params: dict[str, Any] = Field(default_factory=dict)


class ActionPlan(BaseModel):
    intent: IntentType
    device_id: UUID
    steps: list[ActionStep]
    execution_mode: str = "api"  # "api" | "ssh"
    rule_spec: RuleSpecModel | None = None
    nat_spec: NatSpecModel | None = None
    route_spec: RouteSpecModel | None = None
    group_spec: GroupSpecModel | None = None
    content_filter_spec: ContentFilterSpecModel | None = None
    security_service_spec: SecurityServiceSpec | None = None
    security_exclusion_spec: SecurityExclusionSpec | None = None
    app_rules_spec: AppRulesSpec | None = None
    ssh_commands: list[str] | None = None
    raw_intent_data: dict[str, Any] = Field(default_factory=dict)
