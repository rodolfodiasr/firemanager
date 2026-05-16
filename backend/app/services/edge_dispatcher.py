"""
Edge Dispatcher — detecta se um device usa connection_mode='edge' e despacha
o job pelo WebSocket para o Edge Agent responsável.

Se connection_mode='direct' (padrão), retorna None e o caller usa a conexão
SSH/REST direta normalmente.
"""


async def dispatch_if_edge(
    device,
    job_type: str,
    payload: dict,
    timeout: float = 30.0,
) -> dict | None:
    """
    Retorna resultado via Edge Agent se connection_mode='edge'.
    Retorna None se 'direct' (caller usa conexão direta normal).

    Args:
        device: objeto ORM Device com atributos connection_mode e edge_agent_id
        job_type: tipo do job (ex: 'ssh_command', 'rest_call', 'ping')
        payload: dados adicionais do job (host, command, url, etc.)
        timeout: segundos para aguardar resposta do Edge Agent

    Returns:
        dict com o resultado do Edge Agent, ou None para modo direto

    Raises:
        ValueError: se connection_mode='edge' mas edge_agent_id não estiver definido,
                    ou se o Edge Agent não estiver conectado
        TimeoutError: se o Edge Agent não responder dentro do timeout
    """
    if getattr(device, "connection_mode", "direct") != "edge":
        return None

    if not device.edge_agent_id:
        raise ValueError(
            f"Device {device.id} tem connection_mode='edge' mas sem edge_agent_id"
        )

    from app.api.edge_gateway import send_job

    return await send_job(
        agent_id=str(device.edge_agent_id),
        job={"type": job_type, "device_id": str(device.id), **payload},
        timeout=timeout,
    )
