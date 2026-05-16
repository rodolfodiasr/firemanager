"""
Edge Agent Heartbeat — mantém o WebSocket vivo enviando pings periódicos.

Cloudflare fecha conexões WebSocket sem atividade após 100s — o heartbeat
a cada 30s garante que a conexão permanece ativa.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_heartbeat(ws, interval: int = 30):
    """
    Envia pings periódicos pelo WebSocket para manter a conexão ativa.

    Args:
        ws: websocket connection (websockets.WebSocketClientProtocol)
        interval: intervalo em segundos entre pings (default: 30s)
    """
    while True:
        await asyncio.sleep(interval)
        try:
            await ws.ping()
        except Exception as exc:
            logger.debug("Heartbeat failed: %s", exc)
            break
