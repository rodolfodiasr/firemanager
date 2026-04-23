from app.connectors.base import BaseConnector
from app.connectors.fortinet import FortinetConnector
from app.connectors.sonicwall import SonicWallConnector
from app.models.device import Device, VendorEnum
from app.utils.crypto import decrypt_credentials


def get_connector(device: Device) -> BaseConnector:
    creds = decrypt_credentials(device.encrypted_credentials)

    if device.vendor == VendorEnum.fortinet:
        return FortinetConnector(
            host=f"{'https' if device.use_ssl else 'http'}://{device.host}:{device.port}",
            token=creds.get("token", ""),
            vdom=creds.get("vdom", "root"),
            verify_ssl=device.verify_ssl,
        )

    if device.vendor == VendorEnum.sonicwall:
        os_version = int(str(creds.get("os_version", "7"))[0])
        return SonicWallConnector(
            host=f"{'https' if device.use_ssl else 'http'}://{device.host}:{device.port}",
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            os_version=os_version,
            verify_ssl=device.verify_ssl,
        )

    raise NotImplementedError(f"Connector not implemented for vendor: {device.vendor}")
