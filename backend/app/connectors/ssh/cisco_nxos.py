from app.connectors.ssh.base import BaseSSHConnector


class CiscoNXOSConnector(BaseSSHConnector):
    """Cisco NX-OS (Nexus) — no enable required, copy run start via save_config."""

    netmiko_device_type = "cisco_nxos"
    needs_enable = False
    auto_save = True
