import json
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.remediation import (
    CommandStatus,
    RemediationCommand,
    RemediationPlan,
    RemediationRisk,
    RemediationStatus,
)
from app.models.server import Server, ServerOsType
from app.utils.crypto import decrypt_credentials

# Commands that must never be executed regardless of context
_BLOCKLIST = re.compile(
    r"""(
        rm\s+-rf\s+/[^/\s]?[\s$]     # rm -rf /
      | rm\s+-rf\s+/*\s*$             # rm -rf /*
      | dd\s+.*of=/dev/               # dd to block device
      | mkfs                          # format filesystem
      | fdisk\s                       # disk partition tool
      | parted\s                      # partition tool
      | :\(\)\{.*\}                   # fork bomb
      | shutdown\s+-[hPr].*now        # immediate shutdown
      | halt\b                        # halt
      | poweroff\b                    # poweroff
      | reboot\b                      # reboot
      | format\s+[a-z]:               # Windows format drive
    )""",
    re.IGNORECASE | re.VERBOSE,
)

_SYSTEM_PROMPT = """\
You are a senior Linux/Windows infrastructure engineer.
The user will describe a remediation task for a server.
Respond ONLY with a valid JSON object — no markdown, no explanation — with this structure:
{
  "summary": "one-paragraph description of the plan",
  "commands": [
    {
      "order": 1,
      "description": "what this command does",
      "command": "exact shell command to run",
      "risk": "low|medium|high"
    }
  ]
}

Rules:
- Include only commands that fix the described problem.
- Use read-only commands for verification steps.
- Mark any command that modifies files, services, or packages as medium or high risk.
- Never include commands that could destroy data or make the server unresponsive.
- Keep the command list concise (max 10 steps).
- For Windows servers use PowerShell syntax; for Linux use bash/sh.
"""


_SYSTEM_PROMPT_CORRECTIVE = """\
You are a senior infrastructure engineer analyzing the complete results of an executed remediation plan.
The user ran a series of commands on a server and is observing a problem with the final state.

Respond ONLY with a valid JSON object — no markdown, no explanation — with this structure:
{
  "summary": "one-paragraph analysis of what went wrong and the corrective strategy",
  "commands": [
    {
      "order": 1,
      "description": "what this command does",
      "command": "exact shell command to run",
      "risk": "low|medium|high"
    }
  ]
}

Rules:
- Analyze ALL command outputs — a command may return exit 0 but leave the system in a bad state
- Use the user's observation to understand the actual symptom, not just exit codes
- Start with diagnostic/read-only commands to confirm current state, then corrective actions
- For Windows servers use PowerShell syntax; for Linux use bash/sh
- Keep the command list concise (max 12 steps)
- Never include commands that could destroy data or make the server unresponsive
"""


def _is_dangerous(command: str) -> bool:
    return bool(_BLOCKLIST.search(command))


def _parse_ai_json(raw: str) -> dict:
    """Parse JSON from AI response with fallback extraction. Raises RuntimeError on failure."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise RuntimeError(f"A IA retornou uma resposta inválida (não foi possível extrair JSON). Tente novamente.")


async def generate_plan(
    db: AsyncSession,
    tenant_id: UUID,
    server_id: UUID,
    request: str,
    session_id: UUID | None = None,
) -> RemediationPlan:
    result = await db.execute(
        select(Server).where(Server.id == server_id, Server.tenant_id == tenant_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise ValueError("Servidor não encontrado")

    os_hint = "Windows Server (use PowerShell)" if server.os_type == ServerOsType.windows else "Linux (use bash/sh)"
    user_msg = f"OS: {os_hint}\nServer: {server.name} ({server.host})\n\nTask: {request}"

    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    data = _parse_ai_json(raw)
    summary = data.get("summary", "")
    raw_commands = data.get("commands", [])

    plan = RemediationPlan(
        tenant_id=tenant_id,
        server_id=server_id,
        session_id=session_id,
        request=request,
        summary=summary,
        status=RemediationStatus.pending_approval,
    )
    db.add(plan)
    await db.flush()

    for item in raw_commands:
        cmd_text = item.get("command", "")
        if _is_dangerous(cmd_text):
            continue
        risk_val = item.get("risk", "low")
        if risk_val not in ("low", "medium", "high"):
            risk_val = "low"
        cmd = RemediationCommand(
            plan_id=plan.id,
            order=item.get("order", 0),
            description=item.get("description", ""),
            command=cmd_text,
            risk=RemediationRisk(risk_val),
            status=CommandStatus.pending,
        )
        db.add(cmd)

    await db.flush()
    loaded = await get_plan(db, tenant_id, plan.id)
    assert loaded is not None
    return loaded


async def get_plan(db: AsyncSession, tenant_id: UUID, plan_id: UUID) -> RemediationPlan | None:
    result = await db.execute(
        select(RemediationPlan)
        .options(selectinload(RemediationPlan.commands))
        .where(RemediationPlan.id == plan_id, RemediationPlan.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def list_plans(db: AsyncSession, tenant_id: UUID) -> list[RemediationPlan]:
    result = await db.execute(
        select(RemediationPlan)
        .options(selectinload(RemediationPlan.commands))
        .where(RemediationPlan.tenant_id == tenant_id)
        .order_by(RemediationPlan.created_at.desc())
    )
    return list(result.scalars().all())


async def update_command(
    db: AsyncSession,
    tenant_id: UUID,
    plan_id: UUID,
    command_id: UUID,
    new_command: str,
    new_description: str | None = None,
) -> RemediationCommand:
    plan = await get_plan(db, tenant_id, plan_id)
    if not plan:
        raise ValueError("Plano não encontrado")
    if plan.status != RemediationStatus.pending_approval:
        raise ValueError("Comandos só podem ser editados antes da execução")
    cmd = next((c for c in plan.commands if c.id == command_id), None)
    if not cmd:
        raise ValueError("Comando não encontrado")
    if cmd.status != CommandStatus.pending:
        raise ValueError("Só é possível editar comandos pendentes")
    if _is_dangerous(new_command):
        raise ValueError("Comando bloqueado por política de segurança")
    cmd.command = new_command
    if new_description is not None:
        cmd.description = new_description
    await db.flush()
    return cmd


async def retry_plan(
    db: AsyncSession,
    tenant_id: UUID,
    plan_id: UUID,
) -> RemediationPlan:
    plan = await get_plan(db, tenant_id, plan_id)
    if not plan:
        raise ValueError("Plano não encontrado")
    if plan.status != RemediationStatus.partial:
        raise ValueError("Retentativa com IA só está disponível para planos com status 'parcial'")

    failed = [c for c in plan.commands if c.status == CommandStatus.failed]
    skipped = [c for c in plan.commands if c.status == CommandStatus.skipped]
    if not failed and not skipped:
        raise ValueError("Nenhum comando falhou ou foi pulado neste plano")

    result_srv = await db.execute(
        select(Server).where(Server.id == plan.server_id, Server.tenant_id == tenant_id)
    )
    server = result_srv.scalar_one_or_none()
    if not server:
        raise ValueError("Servidor não encontrado")

    os_hint = (
        "Windows Server (use PowerShell)"
        if server.os_type == ServerOsType.windows
        else "Linux (use bash/sh)"
    )

    failures_detail = "\n".join(
        f"- command: {c.command}\n  error: {c.output or '(sem saída)'}"
        for c in failed
    )
    skipped_detail = "\n".join(f"- {c.description}: {c.command}" for c in skipped)

    retry_msg = (
        f"OS: {os_hint}\n"
        f"Server: {server.name} ({server.host})\n"
        f"Original task: {plan.request}\n\n"
        f"The following commands FAILED during execution:\n{failures_detail}\n\n"
        f"The following commands were SKIPPED because earlier ones failed:\n{skipped_detail}\n\n"
        "Analyze the error outputs and generate corrected commands that fix the failures "
        "and complete the skipped steps. Only address what failed — do not repeat steps that already succeeded."
    )

    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": retry_msg}],
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    data = _parse_ai_json(raw)
    summary = data.get("summary", "")
    raw_commands = data.get("commands", [])

    new_plan = RemediationPlan(
        tenant_id=tenant_id,
        server_id=plan.server_id,
        session_id=plan.session_id,
        request=f"[Retentativa] {plan.request}",
        summary=summary,
        status=RemediationStatus.pending_approval,
    )
    db.add(new_plan)
    await db.flush()

    for item in raw_commands:
        cmd_text = item.get("command", "")
        if _is_dangerous(cmd_text):
            continue
        risk_val = item.get("risk", "low")
        if risk_val not in ("low", "medium", "high"):
            risk_val = "low"
        db.add(RemediationCommand(
            plan_id=new_plan.id,
            order=item.get("order", 0),
            description=item.get("description", ""),
            command=cmd_text,
            risk=RemediationRisk(risk_val),
            status=CommandStatus.pending,
        ))

    await db.flush()
    loaded = await get_plan(db, tenant_id, new_plan.id)
    assert loaded is not None
    return loaded


async def corrective_plan(
    db: AsyncSession,
    tenant_id: UUID,
    plan_id: UUID,
    observation: str,
) -> RemediationPlan:
    """Generate a corrective plan using the full execution log + user observation."""
    plan = await get_plan(db, tenant_id, plan_id)
    if not plan:
        raise ValueError("Plano não encontrado")

    executed = [c for c in plan.commands if c.executed_at is not None]
    if not executed:
        raise ValueError("Nenhum comando foi executado neste plano ainda")

    result_srv = await db.execute(
        select(Server).where(Server.id == plan.server_id, Server.tenant_id == tenant_id)
    )
    server = result_srv.scalar_one_or_none()
    if not server:
        raise ValueError("Servidor não encontrado")

    os_hint = (
        "Windows Server (use PowerShell)"
        if server.os_type == ServerOsType.windows
        else "Linux (use bash/sh)"
    )

    MAX_OUTPUT = 1500

    def _trim(text: str | None) -> str:
        if not text:
            return "(sem saída)"
        if len(text) <= MAX_OUTPUT:
            return text
        half = MAX_OUTPUT // 2
        return text[:half] + f"\n... [{len(text) - MAX_OUTPUT} chars truncated] ...\n" + text[-half:]

    exec_log = "\n\n".join(
        f"[{c.order}] {c.description}\n"
        f"Status: {c.status.value}\n"
        f"Command: {c.command}\n"
        f"Output:\n{_trim(c.output)}"
        for c in sorted(plan.commands, key=lambda x: x.order)
    )

    corrective_msg = (
        f"OS: {os_hint}\n"
        f"Server: {server.name} ({server.host})\n"
        f"Original task: {plan.request}\n\n"
        f"=== EXECUTION LOG (all commands and outputs) ===\n{exec_log}\n\n"
        f"=== USER OBSERVATION ===\n{observation}\n\n"
        "Based on the execution log and the user's observation, generate a corrective/diagnostic plan."
    )

    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        system=_SYSTEM_PROMPT_CORRECTIVE,
        messages=[{"role": "user", "content": corrective_msg}],
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    data = _parse_ai_json(raw)
    summary = data.get("summary", "")
    raw_commands = data.get("commands", [])

    new_plan = RemediationPlan(
        tenant_id=tenant_id,
        server_id=plan.server_id,
        session_id=plan.session_id,
        request=f"[Corretivo] {plan.request}",
        summary=summary,
        status=RemediationStatus.pending_approval,
    )
    db.add(new_plan)
    await db.flush()

    for item in raw_commands:
        cmd_text = item.get("command", "")
        if _is_dangerous(cmd_text):
            continue
        risk_val = item.get("risk", "low")
        if risk_val not in ("low", "medium", "high"):
            risk_val = "low"
        db.add(RemediationCommand(
            plan_id=new_plan.id,
            order=item.get("order", 0),
            description=item.get("description", ""),
            command=cmd_text,
            risk=RemediationRisk(risk_val),
            status=CommandStatus.pending,
        ))

    await db.flush()
    loaded = await get_plan(db, tenant_id, new_plan.id)
    assert loaded is not None
    return loaded


async def approve_command(
    db: AsyncSession, tenant_id: UUID, plan_id: UUID, command_id: UUID
) -> RemediationCommand:
    plan = await get_plan(db, tenant_id, plan_id)
    if not plan:
        raise ValueError("Plano não encontrado")
    if plan.status == RemediationStatus.executing:
        raise ValueError("Não é possível aprovar comandos durante a execução")
    cmd = next((c for c in plan.commands if c.id == command_id), None)
    if not cmd:
        raise ValueError("Comando não encontrado")
    if cmd.status != CommandStatus.pending:
        raise ValueError(f"Comando já está em estado '{cmd.status.value}'")
    cmd.status = CommandStatus.approved
    await db.flush()
    return cmd


async def reject_command(
    db: AsyncSession, tenant_id: UUID, plan_id: UUID, command_id: UUID, comment: str | None = None
) -> RemediationCommand:
    plan = await get_plan(db, tenant_id, plan_id)
    if not plan:
        raise ValueError("Plano não encontrado")
    if plan.status == RemediationStatus.executing:
        raise ValueError("Não é possível rejeitar comandos durante a execução")
    cmd = next((c for c in plan.commands if c.id == command_id), None)
    if not cmd:
        raise ValueError("Comando não encontrado")
    if cmd.status != CommandStatus.pending:
        raise ValueError(f"Comando já está em estado '{cmd.status.value}'")
    cmd.status = CommandStatus.rejected
    await db.flush()
    return cmd


async def execute_plan(
    db: AsyncSession, tenant_id: UUID, plan_id: UUID
) -> RemediationPlan:
    plan = await get_plan(db, tenant_id, plan_id)
    if not plan:
        raise ValueError("Plano não encontrado")
    if plan.status in (RemediationStatus.executing, RemediationStatus.rejected):
        raise ValueError(f"Plano não pode ser executado no estado '{plan.status.value}'")

    approved_cmds = [c for c in plan.commands if c.status == CommandStatus.approved]
    if not approved_cmds:
        raise ValueError("Nenhum comando aprovado para execução")

    result = await db.execute(
        select(Server).where(Server.id == plan.server_id, Server.tenant_id == tenant_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise ValueError("Servidor não encontrado")

    creds = decrypt_credentials(server.encrypted_credentials)
    plan.status = RemediationStatus.executing
    await db.flush()

    for cmd in sorted(approved_cmds, key=lambda c: c.order):
        cmd.status = CommandStatus.executing
        await db.flush()

        try:
            output = await _run_command(server, creds, cmd.command)
            cmd.output = output
            cmd.status = CommandStatus.completed
        except Exception as exc:
            cmd.output = str(exc)
            cmd.status = CommandStatus.failed

        cmd.executed_at = datetime.now(timezone.utc)
        await db.flush()

    # Recalculate status without touching pending commands — user can approve more later
    has_pending = any(c.status == CommandStatus.pending for c in plan.commands)
    has_failed = any(c.status == CommandStatus.failed for c in plan.commands)

    if has_pending:
        # Still commands waiting to be approved/executed
        plan.status = RemediationStatus.partial if has_failed else RemediationStatus.pending_approval
    elif has_failed:
        plan.status = RemediationStatus.partial
    else:
        plan.status = RemediationStatus.completed

    plan.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    refreshed = await get_plan(db, tenant_id, plan_id)
    assert refreshed is not None
    return refreshed


async def _run_command(server: Server, creds: dict, command: str) -> str:
    import asyncio
    import socket

    try:
        socket.getaddrinfo(server.host, server.ssh_port)
    except socket.gaierror:
        raise ValueError(
            f"Não foi possível resolver o hostname '{server.host}'. "
            "Se for um endereço interno/privado, cadastre o servidor usando o IP em vez do hostname."
        )

    if server.os_type == ServerOsType.windows:
        from app.connectors.winrm_windows import WinRMConnector

        connector = WinRMConnector(
            host=server.host,
            port=server.ssh_port,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            auth_type=creds.get("auth_type", "ntlm"),
            verify_ssl=creds.get("verify_ssl", False),
        )

        def _run():
            import winrm
            s = winrm.Session(
                f"http://{connector.host}:{connector.port}/wsman",
                auth=(connector.username, connector.password),
                transport=connector.auth_type,
            )
            r = s.run_ps(command)
            out = r.std_out.decode("utf-8", errors="replace").strip()
            err = r.std_err.decode("utf-8", errors="replace").strip()
            if err and r.status_code != 0:
                raise RuntimeError(f"Exit {r.status_code}: {err}")
            return out or err

        return await asyncio.to_thread(_run)

    else:
        from app.connectors.ssh_linux import SshLinuxConnector
        import paramiko

        connector = SshLinuxConnector(
            host=server.host,
            port=server.ssh_port,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            private_key=creds.get("private_key", ""),
        )

        def _run():
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            kwargs: dict = {"hostname": connector.host, "port": connector.port, "username": connector.username, "timeout": 30}
            if connector.private_key:
                import io
                pkey = paramiko.RSAKey.from_private_key(io.StringIO(connector.private_key))
                kwargs["pkey"] = pkey
            else:
                kwargs["password"] = connector.password
            client.connect(**kwargs)
            _, stdout, stderr = client.exec_command(command, timeout=60)
            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
            exit_code = stdout.channel.recv_exit_status()
            client.close()
            if exit_code != 0 and not out:
                raise RuntimeError(f"Exit {exit_code}: {err}")
            return out or err

        return await asyncio.to_thread(_run)
