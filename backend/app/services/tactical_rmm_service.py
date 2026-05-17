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


def _normalize_run_response(r: httpx.Response) -> dict:
    """Normaliza a resposta de execução para sempre retornar dict com output/retcode."""
    if not r.text.strip():
        return {"output": "(sem saída)", "retcode": 0}
    try:
        data = r.json()
        if isinstance(data, str):
            return {"output": data, "retcode": 0}
        if isinstance(data, dict):
            return data
        return {"output": str(data), "retcode": 0}
    except Exception:
        return {"output": r.text, "retcode": 0}


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


async def run_script(
    config: dict,
    agent_id: str,
    script_body: str,
    shell: str = "powershell",
    timeout: int = 90,
) -> dict:
    """Executa um script multi-linha no agente via Tactical RMM.

    Tactical RMM's /runscript/ endpoint requires a stored script ID, so inline
    scripts are sent via /cmd/ using PowerShell -EncodedCommand (UTF-16LE base64)
    for PowerShell, or via a temp-file trick for bash.
    """
    if shell in ("powershell", "ps"):
        return await _run_script_encoded_ps(config, agent_id, script_body, timeout)
    return await _run_script_bash(config, agent_id, script_body, timeout)


async def _run_script_encoded_ps(
    config: dict,
    agent_id: str,
    script_body: str,
    timeout: int,
) -> dict:
    """Run a multi-line PowerShell script via cmd/ using -EncodedCommand (base64 UTF-16LE)."""
    import base64
    encoded = base64.b64encode(script_body.encode("utf-16-le")).decode("ascii")
    command = f"powershell.exe -NoProfile -NonInteractive -EncodedCommand {encoded}"
    return await run_command(config, agent_id, command, shell="cmd", timeout=timeout)


async def _run_script_bash(
    config: dict,
    agent_id: str,
    script_body: str,
    timeout: int,
) -> dict:
    """Run a multi-line bash script via cmd/ by writing to a temp file and executing."""
    import base64
    b64 = base64.b64encode(script_body.encode()).decode("ascii")
    command = (
        f'TF=$(mktemp /tmp/rmm_XXXXXX.sh) && '
        f'echo "{b64}" | base64 -d > "$TF" && '
        f'chmod +x "$TF" && bash "$TF"; RC=$?; rm -f "$TF"; exit $RC'
    )
    return await run_command(config, agent_id, command, shell="bash", timeout=timeout)


async def run_command(
    config: dict,
    agent_id: str,
    command: str,
    shell: str = "powershell",
    timeout: int = 30,
) -> dict:
    """Executa um comando rápido no agente via Tactical RMM."""
    base = _base_url(config)
    payload = {
        "cmd": command,
        "shell": shell,
        "timeout": timeout,
        "run_as_user": False,
    }
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=timeout + 20) as client:
        r = await client.post(f"{base}/agents/{agent_id}/cmd/", json=payload, headers=_headers(config))
        r.raise_for_status()
        return _normalize_run_response(r)
