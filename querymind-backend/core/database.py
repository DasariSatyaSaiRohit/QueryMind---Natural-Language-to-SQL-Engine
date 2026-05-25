import logging

from cryptography.fernet import Fernet, InvalidToken

from core.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.ENCRYPTION_KEY
        if isinstance(key, str):
            key = key.encode("utf-8")
        _fernet = Fernet(key)
    return _fernet


def encrypt_connection_string(conn_str: str) -> str:
    """Encrypt a database connection string using Fernet symmetric encryption.

    Returns a URL-safe base64-encoded encrypted string.
    """
    fernet = _get_fernet()
    encrypted_bytes = fernet.encrypt(conn_str.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_connection_string(encrypted: str) -> str:
    """Decrypt a previously encrypted database connection string.

    Raises:
        ValueError: If decryption fails due to key mismatch or corrupted data.
    """
    fernet = _get_fernet()
    try:
        decrypted_bytes = fernet.decrypt(encrypted.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Failed to decrypt connection string: the encryption key may be wrong "
            "or the data is corrupted."
        ) from exc
    except Exception as exc:
        raise ValueError(
            f"Unexpected decryption error: {exc}"
        ) from exc
