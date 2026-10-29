import binascii
import os
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _get_fernet():
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", None)
    if key is None:
        key = os.getenv("FIELD_ENCRYPTION_KEY")
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


def is_encrypted_token(val: str) -> bool:
    """Check if a string is a valid Fernet ciphertext for the configured key."""
    if not val or not isinstance(val, str) or not val.startswith("gAAAAA"):
        return False
    try:
        _get_fernet().decrypt(val.encode())
        return True
    except Exception:
        return False


def encrypt_token(raw_value: str) -> str:
    """
    Encrypt a token string with Fernet.
    - If empty or None, returns as-is.
    - If already encrypted with the configured key, returns as-is without double encrypting.
    - If FIELD_ENCRYPTION_KEY is not configured, raises ValueError (never silently stores plaintext).
    """
    if raw_value is None:
        return None
    if not raw_value:
        return ""
    if not isinstance(raw_value, str):
        raw_value = str(raw_value)

    if is_encrypted_token(raw_value):
        return raw_value

    return encrypt_value(raw_value)


def decrypt_token(val: str) -> str:
    """
    Decrypt a token string.
    - If empty or None, returns as-is.
    - If a Fernet ciphertext starting with 'gAAAAA', decrypts it. If corrupted/invalid, raises InvalidToken.
    - If unencrypted legacy plaintext (e.g. from before encryption was deployed), returns the plaintext.
    """
    if val is None:
        return None
    if not val:
        return ""
    if not isinstance(val, str):
        return val

    if val.startswith("gAAAAA"):
        try:
            return _get_fernet().decrypt(val.encode()).decode()
        except InvalidToken:
            raise
        except Exception as e:
            raise InvalidToken(f"Invalid ciphertext: {e}") from e

    # Fallback for legacy unencrypted records
    try:
        return _get_fernet().decrypt(val.encode()).decode()
    except (InvalidToken, binascii.Error, ValueError):
        return val


class EncryptedTextField(models.TextField):
    """
    A TextField that transparently encrypts values at rest using Fernet
    (FIELD_ENCRYPTION_KEY) and decrypts values upon retrieval from the database,
    preserving full backward compatibility with legacy unencrypted records.
    """

    description = "TextField that transparently encrypts and decrypts values using Fernet"

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return decrypt_token(value)

    def to_python(self, value):
        if value is None:
            return None
        return decrypt_token(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None:
            return None
        if value == "":
            return ""
        return encrypt_token(value)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, path, args, kwargs