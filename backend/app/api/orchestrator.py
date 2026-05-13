"""API — MultiAgentOrchestrator endpoint."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db

router = APIRouter()


class OrchestratorRequest(BaseModel):
    query: str
    operation_id: UUID | None = None
    ad_config: dict | None = None   # contexto opcional de AD para IdentityAgent


class OrchestratorResponse(BaseModel):
    agents_invoked: list[str]
    consolidated_response: str
    overall_confidence: float
    requires_approval: bool
    handoffs: list[dict]
    duration_ms: int
    status: str


@router.post("", response_model=OrchestratorResponse)
async def orchestrate(
    body: OrchestratorRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrchestratorResponse:
    """Roteia uma query de linguagem natural para os sub-agentes corretos em paralelo."""
    from app.agent.orchestrator import MultiAgentOrchestrator

    orch = MultiAgentOrchestrator()
    context: dict = {}
    if body.ad_config:
        context["ad_config"] = body.ad_config

    result = await orch.run(
        query=body.query,
        context=context,
        db=db,
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        operation_id=body.operation_id,
    )

    return OrchestratorResponse(
        agents_invoked=result["agents_invoked"],
        consolidated_response=result["consolidated_response"],
        overall_confidence=result["overall_confidence"],
        requires_approval=result["requires_approval"],
        handoffs=result["handoffs"],
        duration_ms=result["duration_ms"],
        status=result["status"],
    )
