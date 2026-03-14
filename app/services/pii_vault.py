"""PII Vault — password-derived encryption for sensitive identity fields.

Two encryption modes:

1. Password users  — PBKDF2(password, per-user salt) → 32-byte DEK → Fernet
   Even with full DB + server access, admins cannot decrypt without the user's
   password.  The derived key is NEVER stored.

2. OAuth users     — Server Fernet key (ENCRYPTION_KEY env var) used instead,
   because OAuth users have no password. Falls back gracefully to server-key
   mode when no password is available.

Vault schema (pii_vault table via PIIVault model):
    id, user_id, salt (hex), encrypted_data (Fernet token), created_at, updated_at

PII fields stored in the vault JSON blob:
    full_name, email, phone, dob, document_id,
    references (list of {name, email, phone})

Session key:
    After login the decrypted PII map is stored in the session under
    ``session["pii"]`` as a plain dict.  The DEK itself is not persisted.

Usage:
    # Create or update vault on password change / first login
    await upsert_vault(db, user_id=user.id, password="hunter2", pii={...})

    # Decrypt at login
    pii_map = await unlock_vault(db, user_id=user.id, password="hunter2")
    request.session["pii"] = pii_map

    # For OAuth users (no password)
    pii_map = await unlock_vault_server_key(db, user_id=user.id)
    request.session["pii"] = pii_map

    # Read PII from session (returns empty dict if not unlocked)
    pii = get_session_pii(request)
"""

import base64
import json
import logging
import os
from datetime import UTC, datetime

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PIIVault

logger = logging.getLogger(__name__)

# PBKDF2 parameters — OWASP 2024 recommendation for SHA-256
_PBKDF2_ITERATIONS = 600_000
_SALT_BYTES = 16


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte Fernet key from a password + salt via PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def _server_fernet() -> Fernet:
    """Return a Fernet instance using the server ENCRYPTION_KEY."""
    from app.services.crypto import _get_fernet
    return _get_fernet()


def _encrypt_pii(pii: dict, key: bytes) -> str:
    """Encrypt a PII dict to a Fernet token string."""
    plaintext = json.dumps(pii, default=str).encode()
    return Fernet(key).encrypt(plaintext).decode()


def _decrypt_pii(token: str, key: bytes) -> dict:
    """Decrypt a Fernet token back to a PII dict."""
    plaintext = Fernet(key).decrypt(token.encode())
    return json.loads(plaintext)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def upsert_vault(
    db: AsyncSession,
    *,
    user_id: str,
    pii: dict,
    password: str | None = None,
) -> PIIVault:
    """Create or replace the PII vault for a user.

    If ``password`` is given, uses a password-derived key (PBKDF2).
    If ``password`` is None (OAuth user), uses the server Fernet key.
    A fresh salt is generated for each write on password-derived vaults.
    """
    import secrets

    if password:
        salt = secrets.token_bytes(_SALT_BYTES)
        key = _derive_key(password, salt)
        encrypted = _encrypt_pii(pii, key)
        salt_hex = salt.hex()
    else:
        # OAuth users: encrypt directly with the server Fernet key.
        # No per-user salt needed — the server key provides the protection.
        encrypted = _server_fernet().encrypt(json.dumps(pii, default=str).encode()).decode()
        salt_hex = ""

    result = await db.execute(select(PIIVault).where(PIIVault.user_id == user_id))
    vault = result.scalar_one_or_none()
    if vault:
        vault.salt = salt_hex
        vault.encrypted_data = encrypted
        vault.updated_at = datetime.now(UTC)
    else:
        vault = PIIVault(user_id=user_id, salt=salt_hex, encrypted_data=encrypted)
        db.add(vault)

    await db.commit()
    await db.refresh(vault)
    logger.info("PII vault upserted for user_id=%s (password_derived=%s)", user_id, bool(password))
    return vault


async def unlock_vault(
    db: AsyncSession,
    *,
    user_id: str,
    password: str,
) -> dict | None:
    """Decrypt the PII vault using the user's password.

    Returns the PII dict, or None if the vault does not exist or decryption
    fails (wrong password / corrupted data).
    """
    from cryptography.fernet import InvalidToken

    result = await db.execute(select(PIIVault).where(PIIVault.user_id == user_id))
    vault = result.scalar_one_or_none()
    if not vault:
        return None

    # Vault with empty salt was encrypted with the server key
    if not vault.salt:
        return await unlock_vault_server_key(db, user_id=user_id)

    salt = bytes.fromhex(vault.salt)
    key = _derive_key(password, salt)
    try:
        return _decrypt_pii(vault.encrypted_data, key)
    except (InvalidToken, Exception):
        logger.warning("Failed to unlock PII vault for user_id=%s (bad password or corrupt)", user_id)
        return None


async def unlock_vault_server_key(
    db: AsyncSession,
    *,
    user_id: str,
) -> dict | None:
    """Decrypt the PII vault using the server Fernet key (OAuth users)."""
    from cryptography.fernet import InvalidToken

    result = await db.execute(select(PIIVault).where(PIIVault.user_id == user_id))
    vault = result.scalar_one_or_none()
    if not vault:
        return None

    try:
        plaintext = _server_fernet().decrypt(vault.encrypted_data.encode())
        return json.loads(plaintext)
    except (InvalidToken, Exception):
        logger.warning("Failed to unlock PII vault with server key for user_id=%s", user_id)
        return None


def get_session_pii(request) -> dict:
    """Return the PII map stored in the session, or an empty dict."""
    return request.session.get("pii") or {}


def pii_from_user(user) -> dict:
    """Build a minimal PII dict from a User ORM object.

    Used when creating a vault at registration time or when the vault is
    absent and we want to store what we already know.
    """
    return {
        "full_name": user.name or "",
        "email": user.email or "",
        "phone": "",
        "dob": "",
        "document_id": "",
        "country": "",
        "nationality": "",
        "marital_status": "",
        "references": [],
    }
