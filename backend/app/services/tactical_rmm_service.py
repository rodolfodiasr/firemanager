"""Fase 22B — Tactical RMM REST API integration."""
from __future__ import annotations

import httpx


def _headers(config: dict) -> dict:
    return {"X-API-KEY": config["api_key"], "Content-Type": "application/json"}


def _base_url(config: dict) -> str:
    return (config.get("base_url") or config.get("url", "")).rstrip("/")


def _parse_response(r: httpx.Response) -> list | dict:
    if not r.text.strip():
        raise ValueError(f"Resposta vazia do servidor (HTTP {r.status_code}). Verifique URL base e API key.")
    try:
        return r.json()
    except Exception:
        preview = r.text[:300]
        raise ValueError(f"Resposta não é JSON (HTTP {r.status_code}): {preview}")


async def test_connection(config: dict) -> tuple[bool, str]:
    try:
        base = _base_url(config)
        async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=15) as client:
            r = await client.get(f"{base}/accounts/users/", headers=_headers(config))
            r.raise_for_status()
            users = _parse_response(r)
            return True, f"Conexão OK ({len(users)} usuário(s))"
    except Exception as e:
        return False, str(e)


async def list_users(config: dict) -> list[dict]:
    """Retorna agentes gerenciados (endpoints/computadores) do Tactical RMM."""
    base = _base_url(config)
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=30) as client:
        r = await client.get(f"{base}/agents/", headers=_headers(config))
        r.raise_for_status()
        return _parse_response(r)  # type: ignore[return-value]


async def _resolve_agent_pk(
    client: httpx.AsyncClient,
    base: str,
    headers: dict,
    agent_id: str,
) -> str:
    """Tenta obter o pk numérico do agente; retorna o slug se não encontrar."""
    try:
        r = await client.get(f"{base}/agents/{agent_id}/", headers=headers, timeout=10)
        if r.status_code == 200 and r.text.strip():
            data = r.json()
            pk = data.get("id") or data.get("pk")
            if isinstance(pk, int):
                return str(pk)
    except Exception:
        pass
    return agent_id


async def run_script(
    config: dict,
    agent_id: str,
    script_body: str,
    shell: str = "powershell",
    timeout: int = 90,
) -> dict:
    """Executa um script no agente via Tactical RMM."""
    base = _base_url(config)
    headers = _headers(config)
    payload = {
        "code": script_body,
        "interpreter": shell,
        "timeout": timeout,
        "run_as_user": False,
        "env_vars": [],
    }
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=timeout + 20) as client:
        pk = await _resolve_agent_pk(client, base, headers, agent_id)
        r = await client.post(f"{base}/agents/{pk}/runscript/", json=payload, headers=headers)
        r.raise_for_status()
        if not r.text.strip():
            return {"output": "(sem saída)", "retcode": 0}
        try:
            return r.json()
        except Exception:
            return {"output": r.text, "retcode": 0}


async def run_command(
    config: dict,
    agent_id: str,
    command: str,
    shell: str = "powershell",
    timeout: int = 30,
) -> dict:
    """Executa um comando rápido no agente via Tactical RMM."""
    base = _base_url(config)
    headers = _headers(config)
    payload = {
        "shell": shell,
        "command": command,
        "timeout": timeout,
        "run_as_user": False,
    }
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=timeout + 20) as client:
        pk = await _resolve_agent_pk(client, base, headers, agent_id)
        r = await client.post(f"{base}/agents/{pk}/runcommand/", json=payload, headers=headers)
        r.raise_for_status()
        if not r.text.strip():
            return {"output": "(sem saída)", "retcode": 0}
        try:
            return r.json()
        except Exception:
            return {"output": r.text, "retcode": 0}
