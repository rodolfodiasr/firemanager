"""
Edge Agent Executor — recebe um job JSON e roteia para o connector local adequado.

Tipos de job suportados:
  - ssh_command: executa comando via SSH no device local (paramiko)
  - rest_call: faz chamada HTTP/REST ao device local (aiohttp)
  - ping: testa conectividade ICMP ao host
"""
import asyncio
import platform
from typing import Any


async def execute_job(job: dict, config: dict) -> dict:
    """
    Executa um job e retorna o resultado padronizado.

    Args:
        job: dicionário com type, job_id e parâmetros do job
        config: configuração do edge agent (allowed_device_ids, etc.)

    Returns:
        dict com job_id, success, output e error
    """
    job_type = job.get("type", "")
    job_id = job.get("job_id", "")
    try:
        if job_type == "ssh_command":
            output = await _exec_ssh(job)
        elif job_type == "rest_call":
            output = await _exec_rest(job)
        elif job_type == "ping":
            output = await _exec_ping(job)
        else:
            return {
                "job_id": job_id,
                "success": False,
                "output": None,
                "error": f"Unknown type: {job_type}",
            }
        return {"job_id": job_id, "success": True, "output": output, "error": None}
    except Exception as exc:
        return {"job_id": job_id, "success": False, "output": None, "error": str(exc)}


async def _exec_ssh(job: dict) -> str:
    """Executa um comando SSH no host especificado usando paramiko (thread pool)."""

    def _run():
        import paramiko

        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(
            job["host"],
            port=job.get("port", 22),
            username=job["username"],
            password=job.get("password", ""),
            timeout=15,
        )
        _, out, err = c.exec_command(job["command"], timeout=15)
        result = out.read().decode(errors="replace") + err.read().decode(errors="replace")
        c.close()
        return result

    return await asyncio.to_thread(_run)


async def _exec_rest(job: dict) -> Any:
    """Faz uma chamada HTTP/REST ao device local usando aiohttp."""
    import aiohttp

    async with aiohttp.ClientSession() as session:
        async with session.request(
            job.get("method", "GET").upper(),
            job["url"],
            headers=job.get("headers", {}),
            json=job.get("body"),
            ssl=False,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            return {"status": resp.status, "body": await resp.text()}


async def _exec_ping(job: dict) -> str:
    """Testa conectividade ICMP ao host (3 pacotes)."""
    flag = "-n" if platform.system() == "Windows" else "-c"
    proc = await asyncio.create_subprocess_exec(
        "ping",
        flag,
        "3",
        job["host"],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode(errors="replace")
