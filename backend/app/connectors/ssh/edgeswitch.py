from app.connectors.ssh.base import BaseSSHConnector


class EdgeSwitchConnector(BaseSSHConnector):
    """Ubiquiti EdgeSwitch (EdgeMax line) — firmware 1.x/2.x.

    CLI is IOS-style with enable privilege level.
    Uses ubiquiti_edgeswitch Netmiko driver which handles:
      - 'enable' + secret for privileged mode
      - '--More-- or (q)uit' pagination in show commands
      - 'write memory' for save_config()
    """

    netmiko_device_type = "ubiquiti_edgeswitch"
    needs_enable = True
    auto_save = True
