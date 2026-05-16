"""
Edge Agent WebSocket Gateway

Hub WebSocket em /edge-gateway/{token} — cada Edge Agent abre uma conexão sainte
(outbound WSS 443) a partir da LAN do cliente. O backend autentica pelo token SHA-256
e mantém o WebSocket aberto para despachar jobs e receber respostas.
"""
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.edge_agents import EdgeAgent

router = APIRouter()

# agent_id (str UUID) → WebSocket ativo
_connections: dict[str, WebSocket] = {}

# job_id (str UUID) → asyncio.Future aguardando resposta do agent
_pending: dict[str, asyncio.Future] = {}


def get_connection(agent_id: str) -> WebSocket | None:
    """Retorna o WebSocket ativo de um Edge Agent, ou None se offline."""
    return _connections.get(agent_id)


@router.websocket("/edge-gateway/{token}")
async def edge_gateway(token: str, websocket: WebSocket):
    """
    Endpoint WebSocket para Edge Agents.

    Fluxo:
    1. Edge Agent abre conexão WSS 443 com token em plaintext na URL
    2. Backend faz SHA-256 do token e busca no banco
    3. Aceita a conexão e registra o agent como online
    4. Aguarda mensagens JSON com respostas a jobs
    5. Ao desconectar, marca agent como offline
    """
    # 1. SHA-256 do token para lookup seguro
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # 2. Buscar agente no banco
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(EdgeAgent).where(EdgeAgent.token_hash == token_hash)
        )
        agent = result.scalar_one_or_none()

    if not agent:
        await websocket.close(code=4001, reason="Token inválido")
        return

    await websocket.accept()

    agent_id = str(agent.id)
    _connections[agent_id] = websocket

    # Atualizar status, last_seen e ip_address
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(EdgeAgent).where(EdgeAgent.id == agent.id)
        )
        ag = result.scalar_one_or_none()
        if ag:
            ag.status = "online"
            ag.last_seen = datetime.now(timezone.utc)
            client_host = websocket.client.host if websocket.client else None
            if client_host:
                ag.ip_address = client_host
            await db.commit()

    try:
        async for raw in websocket.iter_text():
            try:
                msg = json.loads(raw)
            except Exception:
                continue

            job_id = msg.get("job_id")
            if job_id and job_id in _pending:
                fut = _pending.pop(job_id)
                if not fut.done():
                    fut.set_result(msg)

    except WebSocketDisconnect:
        pass
    finally:
        _connections.pop(agent_id, None)

        # Marcar agent como offline
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(EdgeAgent).where(EdgeAgent.id == agent.id)
            )
            ag = result.scalar_one_or_none()
            if ag:
                ag.status = "offline"
                await db.commit()


async def send_job(agent_id: str, job: dict, timeout: float = 30.0) -> dict:
    """
    Envia um job para o Edge Agent e aguarda a resposta.

    Args:
        agent_id: UUID do EdgeAgent (str)
        job: dicionário com o job (type, device_id, payload)
        timeout: segundos para aguardar resposta

    Returns:
        Dicionário com o resultado retornado pelo Edge Agent

    Raises:
        ValueError: se o agent não estiver conectado
        TimeoutError: se o agent não responder dentro do timeout
    """
    ws = _connections.get(agent_id)
    if not ws:
        raise ValueError(f"Edge Agent {agent_id} não está conectado")

    job_id = str(uuid4())
    job["job_id"] = job_id

    loop = asyncio.get_event_loop()
    fut: asyncio.Future = loop.create_future()
    _pending[job_id] = fut

    await ws.send_text(json.dumps(job))

    try:
        result = await asyncio.wait_for(fut, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        _pending.pop(job_id, None)
        raise TimeoutError(
            f"Edge Agent {agent_id} não respondeu em {timeout}s"
        )
