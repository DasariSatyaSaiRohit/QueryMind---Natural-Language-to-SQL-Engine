import base64
import hashlib
from cryptography.fernet import Fernet
from app.core.config import settings


def _get_fernet() -> Fernet:
    """Derive a 32-byte URL-safe base64 key from the configured ENCRYPTION_KEY."""
    raw = settings.ENCRYPTION_KEY.encode()
    digest = hashlib.sha256(raw).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt(plain_text: str) -> str:
    """Encrypt a string and return a base64-encoded ciphertext."""
    f = _get_fernet()
    return f.encrypt(plain_text.encode()).decode()


def decrypt(cipher_text: str) -> str:
    """Decrypt a base64-encoded ciphertext and return the original string."""
    f = _get_fernet()
    return f.decrypt(cipher_text.encode()).decode()
