"""
Photo storage service.

Local temp storage for session use, Cloudflare R2 for persistence.
Files are stored under user_id folders: {user_id}/photos/{filename}
"""

import os
import shutil
import uuid
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_PHOTO_SIZE = 5 * 1024 * 1024  # 5 MB


class StorageError(Exception):
    pass


def _ensure_user_dir(user_id: str) -> Path:
    """Create and return the user's local upload directory."""
    user_dir = UPLOAD_DIR / user_id / "photos"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def validate_photo(filename: str, file_bytes: bytes) -> None:
    """Validate photo file before storing."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise StorageError(
            f"Invalid file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    if len(file_bytes) > MAX_PHOTO_SIZE:
        raise StorageError(
            f"Photo too large ({len(file_bytes) // 1024}KB). Max: {MAX_PHOTO_SIZE // 1024 // 1024}MB"
        )
    # Basic magic byte check for image files
    if file_bytes[:2] == b'\xff\xd8':
        return  # JPEG
    if file_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return  # PNG
    if file_bytes[:4] == b'RIFF' and file_bytes[8:12] == b'WEBP':
        return  # WebP
    raise StorageError("File does not appear to be a valid image (JPEG, PNG, or WebP)")


def save_photo_local(user_id: str, filename: str, file_bytes: bytes) -> str:
    """
    Save photo to local temp storage under user_id folder.
    Returns the relative path: {user_id}/photos/{unique_filename}
    """
    validate_photo(filename, file_bytes)

    user_dir = _ensure_user_dir(user_id)
    ext = Path(filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex[:12]}{ext}"
    file_path = user_dir / unique_name
    file_path.write_bytes(file_bytes)

    return f"{user_id}/photos/{unique_name}"


def get_photo_local(relative_path: str) -> Path | None:
    """Get the full local path for a stored photo."""
    full_path = UPLOAD_DIR / relative_path
    if full_path.exists() and full_path.is_file():
        return full_path
    return None


def delete_user_photos(user_id: str) -> None:
    """Delete all local photos for a user."""
    user_dir = UPLOAD_DIR / user_id
    if user_dir.exists():
        shutil.rmtree(user_dir)


# --- Cloudflare R2 ---

def _get_r2_client():
    """Create a boto3 S3 client configured for Cloudflare R2."""
    endpoint = os.environ.get("R2_ENDPOINT_URL")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")

    if not all([endpoint, access_key, secret_key]):
        return None

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )


def _get_r2_bucket() -> str | None:
    return os.environ.get("R2_BUCKET")


def upload_photo_r2(user_id: str, relative_path: str, file_bytes: bytes) -> str | None:
    """
    Upload photo to Cloudflare R2.
    Stored as: {user_id}/photos/{filename}
    Returns the R2 object key, or None if R2 is not configured.
    """
    client = _get_r2_client()
    bucket = _get_r2_bucket()
    if not client or not bucket:
        return None

    key = relative_path  # Already in {user_id}/photos/{filename} format

    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=file_bytes,
            ContentType=_content_type(relative_path),
        )
        return key
    except (ClientError, NoCredentialsError) as e:
        raise StorageError(f"R2 upload failed: {e}") from e


def get_photo_url_r2(relative_path: str, expires_in: int = 3600) -> str | None:
    """
    Generate a presigned URL for a photo stored in R2.
    Returns None if R2 is not configured.
    """
    client = _get_r2_client()
    bucket = _get_r2_bucket()
    if not client or not bucket:
        return None

    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": relative_path},
            ExpiresIn=expires_in,
        )
        return url
    except (ClientError, NoCredentialsError):
        return None


def delete_photo_r2(relative_path: str) -> None:
    """Delete a photo from R2."""
    client = _get_r2_client()
    bucket = _get_r2_bucket()
    if not client or not bucket:
        return

    try:
        client.delete_object(Bucket=bucket, Key=relative_path)
    except (ClientError, NoCredentialsError):
        pass


def sync_to_r2(user_id: str, relative_path: str) -> str | None:
    """
    Sync a locally stored photo to R2.
    Returns the R2 key if successful, None if R2 is not configured.
    """
    local_path = get_photo_local(relative_path)
    if not local_path:
        raise StorageError(f"Local file not found: {relative_path}")

    file_bytes = local_path.read_bytes()
    return upload_photo_r2(user_id, relative_path, file_bytes)


def _content_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "application/octet-stream")
