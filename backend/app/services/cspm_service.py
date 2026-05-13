"""F38 — Cloud Security Posture Management service."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cspm import CloudAccount, CloudResource, CloudSecurityFinding


# ── Security checks ──────────────────────────────────────────────────────────

_CHECKS_AWS = [
    {
        "id": "sg-ssh-open-world",
        "title": "Security Group allows SSH (22) from 0.0.0.0/0",
        "severity": "critical",
        "test": lambda r: _rule_open_world(r, 22),
    },
    {
        "id": "sg-rdp-open-world",
        "title": "Security Group allows RDP (3389) from 0.0.0.0/0",
        "severity": "critical",
        "test": lambda r: _rule_open_world(r, 3389),
    },
    {
        "id": "sg-all-traffic-inbound",
        "title": "Security Group allows all inbound traffic (0.0.0.0/0)",
        "severity": "high",
        "test": lambda r: _rule_allow_all(r),
    },
    {
        "id": "sg-no-description",
        "title": "Security Group rule has no description",
        "severity": "low",
        "test": lambda r: _rules_missing_description(r),
    },
]

_CHECKS_AZURE = [
    {
        "id": "nsg-ssh-open-world",
        "title": "NSG allows SSH (22) from Internet",
        "severity": "critical",
        "test": lambda r: _rule_open_world(r, 22),
    },
    {
        "id": "nsg-rdp-open-world",
        "title": "NSG allows RDP (3389) from Internet",
        "severity": "critical",
        "test": lambda r: _rule_open_world(r, 3389),
    },
    {
        "id": "nsg-all-inbound",
        "title": "NSG allows all inbound traffic from Internet",
        "severity": "high",
        "test": lambda r: _rule_allow_all(r),
    },
]

_CHECKS_GCP = [
    {
        "id": "gcp-fw-ssh-open-world",
        "title": "GCP Firewall allows SSH (22) from 0.0.0.0/0",
        "severity": "critical",
        "test": lambda r: _rule_open_world(r, 22),
    },
    {
        "id": "gcp-fw-rdp-open-world",
        "title": "GCP Firewall allows RDP (3389) from 0.0.0.0/0",
        "severity": "critical",
        "test": lambda r: _rule_open_world(r, 3389),
    },
    {
        "id": "gcp-fw-target-all",
        "title": "GCP Firewall rule targets all instances (no target tags)",
        "severity": "high",
        "test": lambda r: _gcp_target_all(r),
    },
]

_CHECKS_BY_PROVIDER = {"aws": _CHECKS_AWS, "azure": _CHECKS_AZURE, "gcp": _CHECKS_GCP}


def _rule_open_world(resource: dict, port: int) -> bool:
    for rule in (resource.get("rules") or {}).get("inbound", []):
        if rule.get("action") in ("allow", "Accept", "ALLOW"):
            src = rule.get("source", rule.get("src", ""))
            dport = rule.get("port", rule.get("to_port"))
            if src in ("0.0.0.0/0", "::/0", "Internet", "Any", "*") and (
                dport is None or str(dport) in (str(port), "0", "-1", "*")
            ):
                return True
    return False


def _rule_allow_all(resource: dict) -> bool:
    for rule in (resource.get("rules") or {}).get("inbound", []):
        if rule.get("action") in ("allow", "Accept", "ALLOW"):
            src = rule.get("source", rule.get("src", ""))
            port = rule.get("port", rule.get("to_port", "*"))
            if src in ("0.0.0.0/0", "::/0", "Internet", "Any", "*") and str(port) in ("*", "-1", "0", "all", "ALL"):
                return True
    return False


def _rules_missing_description(resource: dict) -> bool:
    for direction in ("inbound", "outbound"):
        for rule in (resource.get("rules") or {}).get(direction, []):
            if not rule.get("description"):
                return True
    return False


def _gcp_target_all(resource: dict) -> bool:
    return not bool((resource.get("rules") or {}).get("target_tags"))


# ── Sync helpers ─────────────────────────────────────────────────────────────

def _simulate_aws_resources(account: CloudAccount) -> list[dict]:
    """Returns empty list — real impl uses boto3. Placeholder for SDK integration."""
    return []


def _simulate_azure_resources(account: CloudAccount) -> list[dict]:
    return []


def _simulate_gcp_resources(account: CloudAccount) -> list[dict]:
    return []


_RESOURCE_FETCHERS = {
    "aws": _simulate_aws_resources,
    "azure": _simulate_azure_resources,
    "gcp": _simulate_gcp_resources,
}


async def sync_account(db: AsyncSession, account: CloudAccount) -> dict:
    """
    Syncs cloud resources and evaluates security checks.
    Real SDK calls (boto3/azure-mgmt/google-cloud) go into the respective helpers.
    """
    account.last_sync_status = "syncing"
    await db.flush()

    try:
        fetcher = _RESOURCE_FETCHERS.get(account.provider)
        if not fetcher:
            raise ValueError(f"Provider {account.provider!r} not supported")

        raw_resources = fetcher(account)

        # Upsert cloud_resources
        for res in raw_resources:
            existing = (await db.execute(
                select(CloudResource).where(
                    CloudResource.account_id == account.id,
                    CloudResource.resource_id == res["resource_id"],
                )
            )).scalar_one_or_none()

            if existing:
                existing.resource_name = res.get("resource_name")
                existing.region = res.get("region")
                existing.rules = res.get("rules")
                existing.tags = res.get("tags")
                existing.synced_at = datetime.now(timezone.utc)
            else:
                db.add(CloudResource(
                    id=uuid4(),
                    account_id=account.id,
                    tenant_id=account.tenant_id,
                    resource_type=res["resource_type"],
                    resource_id=res["resource_id"],
                    resource_name=res.get("resource_name"),
                    region=res.get("region"),
                    rules=res.get("rules"),
                    tags=res.get("tags"),
                    synced_at=datetime.now(timezone.utc),
                ))

        # Evaluate checks
        checks = _CHECKS_BY_PROVIDER.get(account.provider, [])
        findings_created = 0
        for res in raw_resources:
            for check in checks:
                if check["test"](res):
                    # Upsert finding
                    existing_f = (await db.execute(
                        select(CloudSecurityFinding).where(
                            CloudSecurityFinding.account_id == account.id,
                            CloudSecurityFinding.resource_id == res["resource_id"],
                            CloudSecurityFinding.check_id == check["id"],
                        )
                    )).scalar_one_or_none()
                    if not existing_f:
                        db.add(CloudSecurityFinding(
                            id=uuid4(),
                            account_id=account.id,
                            tenant_id=account.tenant_id,
                            resource_type=res["resource_type"],
                            resource_id=res["resource_id"],
                            resource_name=res.get("resource_name"),
                            check_id=check["id"],
                            check_title=check["title"],
                            severity=check["severity"],
                            status="open",
                            details={"resource": res},
                        ))
                        findings_created += 1
                    elif existing_f.status == "resolved":
                        existing_f.status = "open"
                        existing_f.resolved_at = None

        account.last_sync_at = datetime.now(timezone.utc)
        account.last_sync_status = "ok"
        await db.flush()
        await db.refresh(account)
        await db.commit()

        return {
            "resources_synced": len(raw_resources),
            "findings_created": findings_created,
            "status": "ok",
        }

    except Exception as exc:
        account.last_sync_status = "error"
        await db.commit()
        raise exc


async def accept_finding(
    db: AsyncSession,
    finding: CloudSecurityFinding,
    user_id: UUID,
    reason: str,
) -> CloudSecurityFinding:
    finding.status = "accepted"
    finding.accepted_by = user_id
    finding.accepted_reason = reason
    await db.flush()
    await db.refresh(finding)
    await db.commit()
    return finding


async def resolve_finding(db: AsyncSession, finding: CloudSecurityFinding) -> CloudSecurityFinding:
    finding.status = "resolved"
    finding.resolved_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(finding)
    await db.commit()
    return finding
