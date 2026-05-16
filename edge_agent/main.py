"""
FireManager Edge Agent — conecta ao servidor via WebSocket sainte (outbound WSS 443).
Zero porta inbound — funciona atrás de CGNAT.

Uso:
    python -m edge_agent.main --token TOKEN --server wss://app.io/edge-gateway

Docker:
    docker run -d --name fm-edge --restart always \\
        firemanager/edge-agent:latest \\
        --token TOKEN_GERADO_NA_PLATAFORMA \\
        --server wss://firemanager.io/edge-gateway
"""
import argparse
import asyncio
import json
import logging
import sys

import websockets
from websockets.exceptions import ConnectionClosed

from .executor import execute_job
from .heartbeat import run_heartbeat
from .security import validate_device_id

logger = logging.getLogger("fm-edge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Backoff exponencial em segundos: 1, 2, 4, 8, 16, 30 (máximo)
_BACKOFF = [1, 2, 4, 8, 16, 30]


async def _run_session(token: str, server_url: str, config: dict):
    """Executa uma sessão WebSocket completa com o servidor FireManager."""
    url = f"{server_url}/{token}"
    logger.info("Conectando a %s ...", server_url)
    async with websockets.connect(url, ping_interval=None) as ws:
        logger.info("Conectado. Aguardando jobs...")
        hb = asyncio.create_task(run_heartbeat(ws, 30))
        try:
            async for raw in ws:
                job = json.loads(raw)
                logger.info(
                    "Job recebido: type=%s device=%s job_id=%s",
                    job.get("type"),
                    job.get("device_id"),
                    job.get("job_id"),
                )
                allowed = config.get("allowed_device_ids")
                if not validate_device_id(str(job.get("device_id", "")), allowed or []):
                    logger.warning("Device %s não está na allowlist — ignorando", job.get("device_id"))
                    continue
                result = await execute_job(job, config)
                await ws.send(json.dumps(result))
                logger.info(
                    "Job %s concluído: success=%s",
                    job.get("job_id"),
                    result.get("success"),
                )
        finally:
            hb.cancel()
            try:
                await hb
            except asyncio.CancelledError:
                pass


async def run(token: str, server_url: str, config: dict):
    """Loop de reconexão com backoff exponencial."""
    attempt = 0
    while True:
        try:
            await _run_session(token, server_url, config)
            attempt = 0  # reset após sessão bem sucedida
        except (ConnectionClosed, OSError, Exception) as exc:
            delay = _BACKOFF[min(attempt, len(_BACKOFF) - 1)]
            logger.warning(
                "Desconectado (%s). Reconectando em %ds... (tentativa %d)",
                exc,
                delay,
                attempt + 1,
            )
            await asyncio.sleep(delay)
            attempt += 1


def main():
    parser = argparse.ArgumentParser(
        description="FireManager Edge Agent — conecta ao SaaS via WebSocket sainte"
    )
    parser.add_argument(
        "--token",
        required=True,
        help="Token de autenticação gerado na plataforma FireManager",
    )
    parser.add_argument(
        "--server",
        required=True,
        help="URL base do servidor (ex: wss://firemanager.io/edge-gateway)",
    )
    parser.add_argument(
        "--allow-devices",
        nargs="*",
        help="Lista de device UUIDs permitidos (sem argumento = todos permitidos)",
    )
    args = parser.parse_args()

    config = {"allowed_device_ids": args.allow_devices}

    logger.info("FireManager Edge Agent iniciando...")
    if args.allow_devices:
        logger.info("Allowlist de devices: %s", args.allow_devices)
    else:
        logger.info("Allowlist de devices: todos permitidos")

    try:
        asyncio.run(run(args.token, args.server, config))
    except KeyboardInterrupt:
        logger.info("Edge Agent encerrado.")
        sys.exit(0)


if __name__ == "__main__":
    main()
