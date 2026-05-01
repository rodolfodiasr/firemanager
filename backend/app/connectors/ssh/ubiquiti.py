from app.connectors.ssh.base import BaseSSHConnector


class UbiquitiConnector(BaseSSHConnector):
    """Ubiquiti EdgeOS / EdgeSwitch — 'commit' and 'save' are in commands themselves."""

    netmiko_device_type = "ubiquiti_edge"
    needs_enable = False
    auto_save = False
