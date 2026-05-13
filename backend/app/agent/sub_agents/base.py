"""Protocolo base para todos os sub-agentes do orquestrador."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentHandoff:
    """Retorno estruturado de cada sub-agente ao orquestrador."""
    agent: str
    success: bool
    result: dict[str, Any] = field(default_factory=dict)
    actions_taken: list[str] = field(default_factory=list)
    requires_approval: bool = False
    confidence: float = 1.0
    error: str | None = None
    next_steps: list[str] = field(default_factory=list)


class BaseSubAgent:
    """Interface base para sub-agentes especializados."""

    name: str = "base"

    async def can_handle(self, query: str) -> bool:
        raise NotImplementedError

    async def handle(
        self,
        query: str,
        context: dict[str, Any],
    ) -> AgentHandoff:
        raise NotImplementedError
