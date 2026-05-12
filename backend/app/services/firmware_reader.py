"""Reads current firmware version from managed devices via REST or SSH."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.device import Device


class FirmwareInfo:
    def __init__(self, version: str, vendor_label: str, model: str | None = None,
                 build: str | None = None, read_method: str = "rest", raw: str | None = None):
        self.version = version
        self.vendor_label = vendor_label
        self.model = model
        self.build = build
        self.read_method = read_method
        self.raw = raw


async def read_firmware(device: "Device") -> FirmwareInfo | None:
    """Return firmware info for a device, or None if unsupported/unreachable."""
    vendor = device.vendor.value if hasattr(device.vendor, "value") else str(device.vendor)
    reader = _READERS.get(vendor)
    if not reader:
        return None
    try:
        return await reader(device)
    except Exception:
        return None


# ── Fortinet ─────────────────────────────────────────────────────────────────

async def _read_fortinet(device: "Device") -> FirmwareInfo | None:
    from app.connectors.factory import get_connector
    conn = get_connector(device)
    data = await conn.get_system_status()
    version = data.get("version") or data.get("Version") or ""
    if not version:
        return None
    return FirmwareInfo(
        version=version,
        vendor_label="FortiOS",
        model=data.get("model") or data.get("Model"),
        build=data.get("build") or data.get("Build"),
        read_method="rest",
        raw=str(data),
    )


# ── SonicWall ────────────────────────────────────────────────────────────────

async def _read_sonicwall(device: "Device") -> FirmwareInfo | None:
    from app.connectors.factory import get_connector
    conn = get_connector(device)
    data = await conn.get_system_status()
    version = data.get("firmware_version") or data.get("version") or ""
    if not version:
        return None
    return FirmwareInfo(
        version=version,
        vendor_label="SonicOS",
        model=data.get("model"),
        read_method="rest",
        raw=str(data),
    )


# ── pfSense / OPNsense ───────────────────────────────────────────────────────

async def _read_pfsense(device: "Device") -> FirmwareInfo | None:
    from app.connectors.factory import get_connector
    conn = get_connector(device)
    data = await conn.get_system_status()
    version = data.get("version") or ""
    if not version:
        return None
    return FirmwareInfo(
        version=version,
        vendor_label="pfSense",
        read_method="rest",
        raw=str(data),
    )


async def _read_opnsense(device: "Device") -> FirmwareInfo | None:
    from app.connectors.factory import get_connector
    conn = get_connector(device)
    data = await conn.get_system_status()
    version = data.get("product_version") or data.get("version") or ""
    if not version:
        return None
    return FirmwareInfo(
        version=version,
        vendor_label="OPNsense",
        read_method="rest",
        raw=str(data),
    )


# ── MikroTik ─────────────────────────────────────────────────────────────────

async def _read_mikrotik(device: "Device") -> FirmwareInfo | None:
    from app.connectors.factory import get_connector
    conn = get_connector(device)
    data = await conn.get_system_status()
    version = data.get("version") or ""
    if not version:
        return None
    return FirmwareInfo(
        version=version,
        vendor_label="RouterOS",
        model=data.get("board-name"),
        read_method="rest",
        raw=str(data),
    )


# ── Cisco IOS / NX-OS (SSH) ──────────────────────────────────────────────────

async def _read_cisco_ssh(device: "Device", vendor_label: str) -> FirmwareInfo | None:
    from app.connectors.factory import get_ssh_connector
    conn = get_ssh_connector(device)
    output = await conn.execute_command("show version")
    if not output:
        return None
    version = _parse_cisco_version(output)
    if not version:
        return None
    return FirmwareInfo(
        version=version,
        vendor_label=vendor_label,
        read_method="ssh",
        raw=output,
    )


def _parse_cisco_version(output: str) -> str | None:
    patterns = [
        r"Cisco IOS Software.*Version\s+([\d.()A-Za-z]+)",
        r"NX-OS\s+\S+\s+Version\s+([\d.()A-Za-z]+)",
        r"Version\s+([\d.()A-Za-z]+)",
    ]
    for pat in patterns:
        m = re.search(pat, output, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


# ── Juniper (SSH) ─────────────────────────────────────────────────────────────

async def _read_juniper(device: "Device") -> FirmwareInfo | None:
    from app.connectors.factory import get_ssh_connector
    conn = get_ssh_connector(device)
    output = await conn.execute_command("show version")
    if not output:
        return None
    m = re.search(r"Junos:\s*([\d.A-Z]+)", output, re.IGNORECASE)
    version = m.group(1) if m else None
    if not version:
        return None
    return FirmwareInfo(
        version=version,
        vendor_label="Junos",
        read_method="ssh",
        raw=output,
    )


# ── Aruba / HP Comware / Dell (SSH) ──────────────────────────────────────────

async def _read_aruba(device: "Device") -> FirmwareInfo | None:
    from app.connectors.factory import get_ssh_connector
    conn = get_ssh_connector(device)
    output = await conn.execute_command("show version")
    if not output:
        return None
    m = re.search(r"Version\s*:\s*([\d.A-Za-z]+)", output, re.IGNORECASE)
    version = m.group(1) if m else None
    if not version:
        return None
    return FirmwareInfo(version=version, vendor_label="ArubaOS", read_method="ssh", raw=output)


async def _read_hp_comware(device: "Device") -> FirmwareInfo | None:
    from app.connectors.factory import get_ssh_connector
    conn = get_ssh_connector(device)
    output = await conn.execute_command("display version")
    if not output:
        return None
    m = re.search(r"Version\s+([\d.A-Za-z]+)", output, re.IGNORECASE)
    version = m.group(1) if m else None
    if not version:
        return None
    return FirmwareInfo(version=version, vendor_label="Comware", read_method="ssh", raw=output)


async def _read_dell_n(device: "Device") -> FirmwareInfo | None:
    from app.connectors.factory import get_ssh_connector
    conn = get_ssh_connector(device)
    output = await conn.execute_command("show version")
    if not output:
        return None
    m = re.search(r"Version\s*:\s*([\d.]+)", output, re.IGNORECASE)
    version = m.group(1) if m else None
    if not version:
        return None
    return FirmwareInfo(version=version, vendor_label="DNOS", read_method="ssh", raw=output)


# ── Palo Alto (REST) ──────────────────────────────────────────────────────────

async def _read_palo_alto(device: "Device") -> FirmwareInfo | None:
    from app.connectors.factory import get_connector
    conn = get_connector(device)
    data = await conn.get_system_status()
    version = data.get("sw-version") or data.get("version") or ""
    if not version:
        return None
    return FirmwareInfo(
        version=version,
        vendor_label="PAN-OS",
        model=data.get("model"),
        read_method="rest",
        raw=str(data),
    )


# ── Check Point (REST) ────────────────────────────────────────────────────────

async def _read_checkpoint(device: "Device") -> FirmwareInfo | None:
    from app.connectors.factory import get_connector
    conn = get_connector(device)
    data = await conn.get_system_status()
    version = data.get("version") or ""
    if not version:
        return None
    return FirmwareInfo(
        version=version,
        vendor_label="CheckPoint GAIA",
        read_method="rest",
        raw=str(data),
    )


# ── Cisco ASA (SSH) ───────────────────────────────────────────────────────────

async def _read_cisco_asa(device: "Device") -> FirmwareInfo | None:
    return await _read_cisco_ssh(device, "ASA")


# ── Registry ──────────────────────────────────────────────────────────────────

_READERS = {
    "fortinet": _read_fortinet,
    "sonicwall": _read_sonicwall,
    "pfsense": _read_pfsense,
    "opnsense": _read_opnsense,
    "mikrotik": _read_mikrotik,
    "cisco_ios": lambda d: _read_cisco_ssh(d, "IOS"),
    "cisco_nxos": lambda d: _read_cisco_ssh(d, "NX-OS"),
    "cisco_asa": _read_cisco_asa,
    "juniper": _read_juniper,
    "aruba": _read_aruba,
    "hp_comware": _read_hp_comware,
    "dell_n": _read_dell_n,
    "palo_alto": _read_palo_alto,
    "checkpoint": _read_checkpoint,
}
