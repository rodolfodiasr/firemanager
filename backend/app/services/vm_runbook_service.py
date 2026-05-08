"""Fase 27 — AI-powered VM migration runbook generator."""
from __future__ import annotations

import asyncio
import json

import anthropic

from app.config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


async def generate_migration_runbook(
    vms: list[dict],
    source_hypervisor: str,
    target_hypervisor: str,
    tenant_name: str,
) -> str:
    """Generate a migration runbook using Claude AI."""
    vm_summary = json.dumps(
        [
            {
                "name": vm.get("vm_name"),
                "os": vm.get("os_type"),
                "cpu": vm.get("cpu_count"),
                "ram_mb": vm.get("ram_mb"),
                "disk_gb": vm.get("disk_gb"),
                "state": vm.get("power_state"),
                "ips": vm.get("ip_addresses", []),
            }
            for vm in vms
        ],
        indent=2,
    )

    prompt = f"""You are a senior infrastructure engineer creating a VM migration runbook.

Tenant: {tenant_name}
Source: {source_hypervisor}
Target: {target_hypervisor}

VMs to migrate:
{vm_summary}

Generate a comprehensive migration runbook in Markdown format covering:
1. Pre-migration checklist
2. Suggested migration order (grouped by dependencies/risk)
3. Migration steps for each VM group
4. Network configuration changes needed
5. Rollback procedure
6. Post-migration validation tests

Be specific and actionable. Include estimated maintenance windows."""

    def _call() -> str:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    return await asyncio.to_thread(_call)
