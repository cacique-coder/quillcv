"""Dev-only routes. Gated on app.state.dev_mode = True."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException

from app.web.templates import templates

router = APIRouter(prefix="/dev", tags=["dev"])


def _require_dev_mode(request: Request) -> None:
    if not getattr(request.app.state, "dev_mode", False):
        raise HTTPException(status_code=404)


@router.get("/components", response_class=HTMLResponse)
async def components_catalogue(request: Request):
    """Live catalogue of every reusable UI component in canonical + edge states."""
    _require_dev_mode(request)
    return templates.TemplateResponse(
        "dev/components.html",
        {"request": request},
    )
