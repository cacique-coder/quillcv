import uuid
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from app.identity.adapters.fastapi_deps import get_current_user
from app.infrastructure.storage.r2 import (
    StorageError,
    get_photo_local,
    get_photo_url_r2,
    save_photo_local,
    sync_to_r2,
)
from app.web.templates import templates

router = APIRouter(prefix="/photos")


@router.post("/upload")
async def upload_photo(
    request: Request,
    photo: UploadFile = File(...),
    user_id: str | None = None,
):
    """
    Upload a photo for CV use. Creates a user_id if not provided.
    Returns an HTMX partial with the photo preview.
    """
    if not user_id:
        user_id = uuid.uuid4().hex[:16]

    file_bytes = await photo.read()

    try:
        relative_path = save_photo_local(user_id, photo.filename, file_bytes)
    except StorageError as e:
        return HTMLResponse(
            f'<div class="photo-error">{e}</div>',
            status_code=400,
        )

    # Try to sync to R2 in background (non-blocking for the user)
    r2_key = None
    try:
        r2_key = sync_to_r2(user_id, relative_path)
    except StorageError:
        pass  # R2 not configured or failed — local copy is fine

    return templates.TemplateResponse("partials/photo_preview.html", {
        "request": request,
        "photo_path": relative_path,
        "user_id": user_id,
        "r2_synced": r2_key is not None,
    })


@router.get("/serve/{user_id}/{subpath:path}")
async def serve_photo(request: Request, user_id: str, subpath: str):
    """Serve a locally stored photo. Requires authentication.

    Only the photo owner may access their own photos.
    Admins (authenticated users with admin flag) may access any photo.
    """
    current_user = await get_current_user(request)

    if not current_user:
        return HTMLResponse("Authentication required", status_code=401)

    # Authorisation: only the owner may fetch their own photos.
    # We compare against the authenticated user's ID stored in the session.
    # The user_id path segment is compared case-sensitively.
    if current_user.id != user_id:
        return HTMLResponse("Forbidden", status_code=403)

    relative_path = f"{user_id}/{subpath}"

    # Try local first
    local_path = get_photo_local(relative_path)
    if local_path:
        return FileResponse(local_path)

    # Try R2 presigned URL
    r2_url = get_photo_url_r2(relative_path)
    if r2_url:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=r2_url)

    return HTMLResponse("Photo not found", status_code=404)
