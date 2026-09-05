import os
from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet():
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", None) or os.getenv("FIELD_ENCRYPTION_KEY")
    if not key:
        raise ValueError("FIELD_ENCRYPTION_KEY is not configured in settings or environment")
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_value(raw_value: str) -> str:
    if not raw_value:
        return ""
    return _get_fernet().encrypt(raw_value.encode()).decode()


def decrypt_value(encrypted_value: str) -> str:
    if not encrypted_value:
        return ""
    return _get_fernet().decrypt(encrypted_value.encode()).decode()