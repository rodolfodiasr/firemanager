from app.connectors.ssh.base import BaseSSHConnector


class DellOS10Connector(BaseSSHConnector):
    """Dell OS10 / PowerSwitch S-Z series — NX-OS style CLI, save via save_config."""

    needs_enable = False
    auto_save = True

    def _device_type(self) -> str:
        os_ver = str(self.credentials.get("os_version", "")).lower()
        if "powerconnect" in os_ver:
            return "dell_powerconnect"
        return "dell_os10"
