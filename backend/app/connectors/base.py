from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConnectionResult:
    success: bool
    latency_ms: float | None = None
    firmware_version: str | None = None
    error: str | None = None


@dataclass
class FirewallRule:
    rule_id: str
    name: str
    src: str
    dst: str
    service: str
    action: str
    enabled: bool
    src_zone: str = ""
    dst_zone: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class NatPolicy:
    rule_id: str
    name: str
    inbound: str
    outbound: str
    source: str
    translated_source: str
    destination: str
    translated_destination: str
    service: str
    translated_service: str
    enabled: bool
    comment: str
    raw: dict = field(default_factory=dict)


@dataclass
class ExecutionResult:
    success: bool
    rule_id: str | None = None
    raw_response: dict | None = None
    error: str | None = None


@dataclass
class RuleSpec:
    name: str
    src_address: str
    dst_address: str
    service: str
    src_zone: str = "LAN"
    dst_zone: str = "WAN"
    action: str = "accept"
    comment: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class NatSpec:
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


@dataclass
class RoutePolicy:
    rule_id: str
    name: str
    interface: str
    source: str
    destination: str
    service: str
    gateway: str
    metric: int
    distance: int
    route_type: str
    comment: str
    enabled: bool
    raw: dict = field(default_factory=dict)


@dataclass
class RouteSpec:
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


@dataclass
class GroupSpec:
    name: str
    members: list[str]
    comment: str | None = None


class BaseConnector(ABC):
    """Abstract interface that every vendor connector must implement."""

    @abstractmethod
    async def test_connection(self) -> ConnectionResult: ...

    @abstractmethod
    async def list_rules(self) -> list[FirewallRule]: ...

    @abstractmethod
    async def create_rule(self, spec: RuleSpec) -> ExecutionResult: ...

    @abstractmethod
    async def create_group(self, spec: GroupSpec) -> ExecutionResult: ...

    @abstractmethod
    async def delete_rule(self, rule_id: str) -> ExecutionResult: ...

    @abstractmethod
    async def edit_rule(self, rule_id: str, spec: RuleSpec) -> ExecutionResult: ...

    @abstractmethod
    async def get_config_snapshot(self) -> str: ...

    @abstractmethod
    async def list_nat_policies(self) -> list[NatPolicy]: ...

    @abstractmethod
    async def create_nat_policy(self, spec: NatSpec) -> ExecutionResult: ...

    @abstractmethod
    async def delete_nat_policy(self, rule_id: str) -> ExecutionResult: ...

    @abstractmethod
    async def list_route_policies(self) -> list[RoutePolicy]: ...

    @abstractmethod
    async def create_route_policy(self, spec: RouteSpec) -> ExecutionResult: ...

    @abstractmethod
    async def delete_route_policy(self, rule_id: str) -> ExecutionResult: ...

    async def get_security_status(self) -> dict:
        """Return status of security services. Vendors that support it override this."""
        return {}
