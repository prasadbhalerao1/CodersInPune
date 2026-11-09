"""Encryption at rest for integration credentials (e.g. Linear/Notion OAuth tokens).

Fernet (AES-128-CBC + HMAC-SHA256) with a server-side key from the environment
(`RELAY_INTEGRATION_ENCRYPTION_KEY`, generate with `Fernet.generate_key()`). Ciphertext
lives in the database; the key never does. Without a key, integrations that need stored
credentials report themselves as not configured.
"""

from cryptography.fernet import Fernet, InvalidToken

from relay.config import Settings


class SecretBoxUnavailableError(Exception):
    pass


def _fernet(settings: Settings) -> Fernet:
    if settings.integration_encryption_key is None:
        raise SecretBoxUnavailableError
    return Fernet(settings.integration_encryption_key.get_secret_value().encode())


def can_encrypt(settings: Settings) -> bool:
    return settings.integration_encryption_key is not None


def encrypt(settings: Settings, plaintext: str) -> str:
    return _fernet(settings).encrypt(plaintext.encode()).decode()


def decrypt(settings: Settings, ciphertext: str) -> str:
    try:
        return _fernet(settings).decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:  # key rotated or data tampered with
        raise SecretBoxUnavailableError from exc
