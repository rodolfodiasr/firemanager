from app.connectors.ssh.base import BaseSSHConnector


class ArubaConnector(BaseSSHConnector):
    """Aruba OS-CX / AOS-Switch — enable required, save via save_config."""

    netmiko_device_type = "aruba_osswitch"
    needs_enable = True
    auto_save = True
