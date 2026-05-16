"""
Edge Agent Security — decriptação de payloads Fernet e validação de device_id.
"""
import json
from cryptography.fernet import Fernet


def decrypt_payload(fernet_key: str, encrypted: str) -> dict:
    """Decripta um payload cifrado com Fernet e retorna como dict."""
    f = Fernet(fernet_key.encode())
    return json.loads(f.decrypt(encrypted.encode()))


def validate_device_id(device_id: str, allowed_ids: list[str]) -> bool:
    """
    Valida se o device_id está na lista de permitidos.
    Se allowed_ids estiver vazio, todos os IDs são permitidos.
    """
    return not allowed_ids or device_id in allowed_ids
