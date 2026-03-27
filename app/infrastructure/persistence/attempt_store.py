"""
Server-side storage for CV generation attempts.

Each attempt stores all wizard state: region, personal details, uploaded documents,
parsed text, AI results (template recommendations), etc. Keyed by attempt_id,
stored as JSON on disk. This avoids re-uploading files and re-calling the AI
when the user navigates back and forth in the wizard.

Security:
- attempt.json is encrypted at rest with the server Fernet key.
- Uploaded document bytes are also encrypted before writing to disk.
- Attempt directories older than ATTEMPT_TTL_DAYS are cleaned up automatically.
  Call cleanup_old_attempts() from a periodic task or on each request.
"""

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from app.infrastructure.crypto import decrypt_data, encrypt_data

logger = logging.getLogger(__name__)

ATTEMPTS_DIR = Path(__file__).parent.parent.parent / "uploads" / "attempts"
ATTEMPT_TTL_DAYS = 7
_SECONDS_PER_DAY = 86_400


def create_attempt() -> str:
    """Create a new empty attempt and return its ID."""
    attempt_id = uuid.uuid4().hex[:16]
    _save(attempt_id, {
        "id": attempt_id,
        "created_at": time.time(),
        "step": 1,
    })
    return attempt_id


def get_attempt(attempt_id: str) -> dict | None:
    """Load attempt data by ID. Returns None if not found."""
    from cryptography.fernet import InvalidToken

    path = _path(attempt_id)
    if not path.exists():
        return None
    try:
        raw = path.read_text()
        # Decrypt if the file is an encrypted token; fall back for legacy plaintext.
        try:
            raw = decrypt_data(raw)
        except (InvalidToken, Exception):
            logger.debug("Decryption skipped for attempt %s — legacy unencrypted file", attempt_id)
        return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return None


def update_attempt(attempt_id: str, **fields: Any) -> dict:
    """Update specific fields on an attempt. Returns the updated attempt."""
    data = get_attempt(attempt_id)
    if data is None:
        data = {"id": attempt_id, "created_at": time.time()}
    data.update(fields)
    data["updated_at"] = time.time()
    _save(attempt_id, data)
    return data


def save_document(attempt_id: str, doc_key: str, filename: str, file_bytes: bytes) -> str:
    """Save an uploaded document to disk (encrypted) and record it in the attempt.

    doc_key: "cv_file" or "extra_doc_0", "extra_doc_1"
    Returns the path relative to the attempt directory.
    """
    attempt_dir = _ensure_dir(attempt_id) / "docs"
    attempt_dir.mkdir(exist_ok=True)

    # Use a stable name based on doc_key so re-uploads overwrite.
    # Store with .enc suffix to signal encryption.
    ext = Path(filename).suffix.lower()
    safe_name = f"{doc_key}{ext}.enc"
    file_path = attempt_dir / safe_name

    # Encrypt the raw bytes via the server key
    encrypted = encrypt_data(file_bytes.hex())  # hex-encode bytes → str → encrypt
    file_path.write_text(encrypted)

    # Record in attempt metadata
    data = get_attempt(attempt_id) or {}
    docs = data.get("documents", {})
    docs[doc_key] = {
        "filename": filename,
        "stored_as": safe_name,
        "size": len(file_bytes),
        "encrypted": True,
    }
    update_attempt(attempt_id, documents=docs)

    return str(file_path)


def get_document_bytes(attempt_id: str, doc_key: str) -> bytes | None:
    """Read a previously stored document's bytes, decrypting if needed."""
    from cryptography.fernet import InvalidToken

    data = get_attempt(attempt_id)
    if not data:
        return None
    docs = data.get("documents", {})
    doc_info = docs.get(doc_key)
    if not doc_info:
        return None

    file_path = _ensure_dir(attempt_id) / "docs" / doc_info["stored_as"]
    if not file_path.exists():
        return None

    if doc_info.get("encrypted"):
        try:
            decrypted_hex = decrypt_data(file_path.read_text())
            return bytes.fromhex(decrypted_hex)
        except (InvalidToken, ValueError, OSError):
            logger.warning("Failed to decrypt document %s/%s", attempt_id, doc_key)
            return None
    else:
        # Legacy unencrypted file
        return file_path.read_bytes()


def get_document_filename(attempt_id: str, doc_key: str) -> str | None:
    """Get the original filename of a stored document."""
    data = get_attempt(attempt_id)
    if not data:
        return None
    docs = data.get("documents", {})
    doc_info = docs.get(doc_key)
    return doc_info["filename"] if doc_info else None


def _path(attempt_id: str) -> Path:
    return _ensure_dir(attempt_id) / "attempt.json"


def _ensure_dir(attempt_id: str) -> Path:
    # Sanitize attempt_id to prevent directory traversal
    safe_id = "".join(c for c in attempt_id if c.isalnum())
    d = ATTEMPTS_DIR / safe_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save(attempt_id: str, data: dict) -> None:
    path = _path(attempt_id)
    plaintext = json.dumps(data, default=str)
    path.write_text(encrypt_data(plaintext))


def cleanup_old_attempts(ttl_days: int = ATTEMPT_TTL_DAYS) -> int:
    """Delete attempt directories older than ``ttl_days`` days.

    Returns the number of directories removed.
    Safe to call at any time; ignores errors on individual directories.
    """
    if not ATTEMPTS_DIR.exists():
        return 0

    cutoff = time.time() - (ttl_days * _SECONDS_PER_DAY)
    removed = 0

    for attempt_dir in ATTEMPTS_DIR.iterdir():
        if not attempt_dir.is_dir():
            continue
        try:
            mtime = attempt_dir.stat().st_mtime
            if mtime < cutoff:
                import shutil
                shutil.rmtree(attempt_dir, ignore_errors=True)
                removed += 1
                logger.info("Cleaned up expired attempt directory: %s", attempt_dir.name)
        except OSError:
            pass

    if removed:
        logger.info("Attempt cleanup: removed %d expired directories (ttl=%dd)", removed, ttl_days)
    return removed
