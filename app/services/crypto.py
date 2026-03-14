"""Server-side Fernet encryption for large files and CV data at rest.

Uses the ENCRYPTION_KEY environment variable (a URL-safe base64-encoded 32-byte
key). Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Usage:
    from app.services.crypto import encrypt_data, decrypt_data

    ciphertext = encrypt_data("sensitive text")
    plaintext  = decrypt_data(ciphertext)
"""

import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Return a module-level Fernet instance, initialised lazily from env."""
    global _fernet
    if _fernet is not None:
        return _fernet

    key = os.environ.get("ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY environment variable is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" "
            "and add it to your .env file. Without a persistent key, encrypted data will be lost on restart."
        )

    _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_data(plaintext: str) -> str:
    """Encrypt a UTF-8 string with the server Fernet key.

    Returns a URL-safe base64 ciphertext string (also UTF-8 safe to store in
    Text columns or on disk).
    """
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_data(ciphertext: str) -> str:
    """Decrypt a Fernet ciphertext string back to plaintext.

    Raises ``cryptography.fernet.InvalidToken`` if the token is corrupted or
    was encrypted with a different key.
    """
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.error("decrypt_data: invalid or corrupted token")
        raise
