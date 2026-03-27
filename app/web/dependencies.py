"""Shared FastAPI dependencies for web routes."""

# Re-export commonly used auth dependencies for convenience
from app.identity.adapters.fastapi_deps import get_current_user, require_auth  # noqa: F401
