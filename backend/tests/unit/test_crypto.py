import pytest

from app.utils.crypto import decrypt_credentials, encrypt_credentials


def test_encrypt_decrypt_roundtrip():
    creds = {"token": "abc123", "vdom": "root", "auth_type": "token"}
    encrypted = encrypt_credentials(creds)
    assert isinstance(encrypted, str)
    assert encrypted != str(creds)
    decrypted = decrypt_credentials(encrypted)
    assert decrypted == creds


def test_different_encryptions_for_same_data():
    creds = {"token": "secret"}
    enc1 = encrypt_credentials(creds)
    enc2 = encrypt_credentials(creds)
    # Fernet uses random IV, so ciphertext should differ
    assert enc1 != enc2
    # But both should decrypt to the same value
    assert decrypt_credentials(enc1) == decrypt_credentials(enc2)
