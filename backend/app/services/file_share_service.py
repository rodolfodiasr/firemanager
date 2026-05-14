"""F36.ext — File Share Governance Service."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_share import FileShareAclEntry, FileShareConfig, FileShareShare
from app.utils.crypto import decrypt_credentials, encrypt_credentials

# PowerShell script executed via Edge Agent to audit shares + ACLs
_PS_AUDIT_SCRIPT = r"""
param([string]$RootPath, [int]$Depth = 2)
$result = @{shares = @(); acls = @()}

# List SMB shares on local machine
$shares = Get-SmbShare -ErrorAction SilentlyContinue | Where-Object {$_.Name -notmatch '^\w+\$$'}
foreach ($share in $shares) {
    $abeEnabled = $null
    try { $abeEnabled = (Get-SmbShare -Name $share.Name).FolderEnumerationMode -eq 'AccessBased' } catch {}
    $shareInfo = @{
        share_name  = $share.Name
        unc_path    = "\\$env:COMPUTERNAME\$($share.Name)"
        description = $share.Description
        abe_enabled = $abeEnabled
    }
    $result.shares += $shareInfo
}

# Collect ACLs recursively up to $Depth
function Get-AclEntries($Path, $CurrentDepth) {
    if ($CurrentDepth -gt $Depth) { return }
    try {
        $acl = Get-Acl -Path $Path -ErrorAction Stop
        foreach ($entry in $acl.Access) {
            $result.acls += @{
                folder_path      = $Path
                principal_name   = $entry.IdentityReference.Value
                principal_type   = if ($entry.IdentityReference -match "\\") { "user" } else { "group" }
                permission_type  = $entry.FileSystemRights.ToString()
                inherited        = $entry.IsInherited
                is_deny          = ($entry.AccessControlType -eq "Deny")
                depth            = $CurrentDepth
            }
        }
        if ($CurrentDepth -lt $Depth) {
            Get-ChildItem -Path $Path -Directory -ErrorAction SilentlyContinue | ForEach-Object {
                Get-AclEntries $_.FullName ($CurrentDepth + 1)
            }
        }
    } catch {}
}

if ($RootPath) { Get-AclEntries $RootPath 0 }
$result | ConvertTo-Json -Depth 5
"""


async def list_configs(db: AsyncSession, tenant_id: UUID) -> list[FileShareConfig]:
    result = await db.execute(
        select(FileShareConfig)
        .where(FileShareConfig.tenant_id == tenant_id)
        .order_by(FileShareConfig.name)
    )
    return list(result.scalars().all())


async def get_config(db: AsyncSession, config_id: UUID, tenant_id: UUID) -> FileShareConfig | None:
    result = await db.execute(
        select(FileShareConfig).where(
            FileShareConfig.id == config_id,
            FileShareConfig.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_config(
    db: AsyncSession,
    tenant_id: UUID,
    name: str,
    server_hostname: str,
    unc_root: str,
    edge_agent_id: UUID | None,
    credentials: dict | None,
    scan_depth: int = 2,
) -> FileShareConfig:
    config = FileShareConfig(
        tenant_id=tenant_id,
        name=name,
        server_hostname=server_hostname,
        unc_root=unc_root,
        edge_agent_id=edge_agent_id,
        config_encrypted=encrypt_credentials(credentials or {}),
        scan_depth=max(1, min(scan_depth, 5)),
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)
    return config


async def delete_config(db: AsyncSession, config: FileShareConfig) -> None:
    await db.delete(config)


async def get_shares(db: AsyncSession, config_id: UUID, tenant_id: UUID) -> list[FileShareShare]:
    result = await db.execute(
        select(FileShareShare).where(
            FileShareShare.config_id == config_id,
            FileShareShare.tenant_id == tenant_id,
        ).order_by(FileShareShare.share_name)
    )
    return list(result.scalars().all())


async def get_acl_entries(
    db: AsyncSession,
    share_id: UUID,
    tenant_id: UUID,
) -> list[FileShareAclEntry]:
    result = await db.execute(
        select(FileShareAclEntry).where(
            FileShareAclEntry.share_id == share_id,
            FileShareAclEntry.tenant_id == tenant_id,
        ).order_by(FileShareAclEntry.folder_path, FileShareAclEntry.principal_name)
    )
    return list(result.scalars().all())


def _assess_health(share_info: dict, acl_entries: list[dict]) -> tuple[str, list[str]]:
    issues = []
    if share_info.get("abe_enabled") is False:
        issues.append("ABE (Access-Based Enumeration) desativado — usuários veem pastas sem acesso")

    dangerous_perms = {"FullControl", "Modify"}
    broad_principals = {"Everyone", "Authenticated Users", "Domain Users", "CREATOR OWNER"}

    for entry in acl_entries:
        perm = entry.get("permission_type", "")
        principal = entry.get("principal_name", "").split("\\")[-1]
        if any(dp in perm for dp in dangerous_perms) and principal in broad_principals:
            issues.append(f"Permissão excessiva: {principal} tem {perm} na pasta {entry.get('folder_path', '')}")

    if issues:
        return ("warning" if len(issues) <= 2 else "error"), issues
    return "ok", []


async def process_scan_result(
    db: AsyncSession,
    config: FileShareConfig,
    scan_data: dict,
) -> dict:
    now = datetime.now(timezone.utc)
    shares_data = scan_data.get("shares", [])
    acls_data = scan_data.get("acls", [])

    await db.execute(delete(FileShareShare).where(FileShareShare.config_id == config.id))

    total_issues = 0
    for share_info in shares_data:
        share_acls = [a for a in acls_data if a.get("folder_path", "").startswith(share_info.get("unc_path", ""))]
        health_status, health_issues = _assess_health(share_info, share_acls)
        total_issues += len(health_issues)

        share = FileShareShare(
            config_id=config.id,
            tenant_id=config.tenant_id,
            share_name=share_info.get("share_name", ""),
            unc_path=share_info.get("unc_path", ""),
            description=share_info.get("description"),
            abe_enabled=share_info.get("abe_enabled"),
            health_status=health_status,
            health_issues=health_issues if health_issues else None,
            acl_count=len(share_acls),
            scanned_at=now,
        )
        db.add(share)
        await db.flush()
        await db.refresh(share)

        for acl_data in share_acls:
            entry = FileShareAclEntry(
                share_id=share.id,
                tenant_id=config.tenant_id,
                folder_path=acl_data.get("folder_path", ""),
                principal_name=acl_data.get("principal_name", ""),
                principal_type=acl_data.get("principal_type", "unknown"),
                permission_type=acl_data.get("permission_type", ""),
                inherited=bool(acl_data.get("inherited", False)),
                is_deny=bool(acl_data.get("is_deny", False)),
                depth=int(acl_data.get("depth", 0)),
            )
            db.add(entry)

    config.last_scan_at = now
    config.last_scan_status = "ok"
    await db.flush()

    return {
        "shares_found": len(shares_data),
        "acl_entries": len(acls_data),
        "issues": total_issues,
    }


def get_powershell_script(unc_root: str, depth: int = 2) -> str:
    return f"$RootPath = '{unc_root}'; $Depth = {depth}\n" + _PS_AUDIT_SCRIPT
