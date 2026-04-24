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
