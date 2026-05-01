from app.connectors.ssh.base import BaseSSHConnector


class CiscoIOSConnector(BaseSSHConnector):
    """Cisco IOS / IOS-XE — enable required, write mem via save_config."""

    netmiko_device_type = "cisco_ios"
    needs_enable = True
    auto_save = True
