from app.connectors.base import BaseConnector
from app.connectors.endian import EndianConnector
from app.connectors.fortinet import FortinetConnector
from app.connectors.mikrotik import MikroTikConnector
from app.connectors.opnsense import OPNsenseConnector
from app.connectors.pfsense import PfSenseConnector
from app.connectors.sonicwall import SonicWallConnector
from app.connectors.sonicwall_ssh import SonicWallSSHConnector
from app.connectors.ssh import (
    ArubaConnector,
    BaseSSHConnector,
    CiscoIOSConnector,
    CiscoNXOSConnector,
    DellNConnector,
    DellOS10Connector,
    HPComwareConnector,
    JuniperConnector,
    UbiquitiConnector,
)
from app.models.device import Device, VendorEnum
from app.utils.crypto import decrypt_credentials

# Vendors managed exclusively via SSH/CLI (no REST API)
CLI_VENDORS = frozenset({
    VendorEnum.cisco_ios,
    VendorEnum.cisco_nxos,
    VendorEnum.juniper,
    VendorEnum.aruba,
    VendorEnum.dell,
    VendorEnum.dell_n,
    VendorEnum.hp_comware,
    VendorEnum.ubiquiti,
})

_SSH_CONNECTOR_MAP: dict[VendorEnum, type[BaseSSHConnector]] = {
    VendorEnum.cisco_ios:  CiscoIOSConnector,
    VendorEnum.cisco_nxos: CiscoNXOSConnector,
    VendorEnum.juniper:    JuniperConnector,
    VendorEnum.aruba:      ArubaConnector,
    VendorEnum.dell:       DellOS10Connector,
    VendorEnum.dell_n:     DellNConnector,
    VendorEnum.hp_comware: HPComwareConnector,
    VendorEnum.ubiquiti:   UbiquitiConnector,
}


def get_ssh_connector(device: Device) -> BaseSSHConnector:
    creds = decrypt_credentials(device.encrypted_credentials)

    if device.vendor == VendorEnum.sonicwall:
        return SonicWallSSHConnector(
            host=device.host,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            ssh_port=int(creds.get("ssh_port", 22)),
        )

    connector_cls = _SSH_CONNECTOR_MAP.get(device.vendor)
    if connector_cls:
        return connector_cls(device=device, credentials=creds)

    raise NotImplementedError(f"SSH connector not implemented for vendor: {device.vendor}")


def get_connector(device: Device) -> BaseConnector:
    creds = decrypt_credentials(device.encrypted_credentials)
    base_url = f"{'https' if device.use_ssl else 'http'}://{device.host}:{device.port}"

    if device.vendor == VendorEnum.fortinet:
        return FortinetConnector(
            host=base_url,
            token=creds.get("token") or "",
            vdom=creds.get("vdom") or "root",
            verify_ssl=device.verify_ssl,
        )

    if device.vendor == VendorEnum.sonicwall:
        os_version = int(str(creds.get("os_version", "7"))[0])
        return SonicWallConnector(
            host=base_url,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            os_version=os_version,
            verify_ssl=device.verify_ssl,
            known_firmware=device.firmware_version,
        )

    if device.vendor == VendorEnum.pfsense:
        return PfSenseConnector(
            host=base_url,
            api_key=creds.get("token", ""),
            verify_ssl=device.verify_ssl,
        )

    if device.vendor == VendorEnum.opnsense:
        return OPNsenseConnector(
            host=base_url,
            api_key=creds.get("username", ""),
            api_secret=creds.get("password", ""),
            verify_ssl=device.verify_ssl,
        )

    if device.vendor == VendorEnum.mikrotik:
        return MikroTikConnector(
            host=base_url,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            verify_ssl=device.verify_ssl,
        )

    if device.vendor == VendorEnum.endian:
        return EndianConnector(
            host=base_url,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            ssh_port=int(creds.get("ssh_port", 22)),
            verify_ssl=device.verify_ssl,
        )

    raise NotImplementedError(f"Connector not implemented for vendor: {device.vendor}")
