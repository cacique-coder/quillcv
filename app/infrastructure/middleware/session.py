"""SQLite-backed server-side session middleware for QuillCV.

Replaces Starlette's cookie-based SessionMiddleware with server-side sessions
stored in a SQLite file at data/sessions.db.  Session data is attached to
``request.state.session`` as a plain dict — the same access pattern as
Starlette's ``request.session``.

Session lifecycle:
- Read session_id from a httponly cookie named "session".
- Load the JSON data blob from SQLite; attach to request.state.session.
- After the response, write back to SQLite only when the session was modified
  (dirty flag).
- Set/refresh the cookie unless the response is publicly cacheable and the session was not modified.
- Destroy: delete the row from SQLite and expire the cookie.
"""

import json
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.infrastructure.middleware.main import session_id_var

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "sessions.db"
_SESSION_TTL_DAYS = 30
_COOKIE_NAME = "session"
_IS_PRODUCTION = os.environ.get("APP_ENV", "development") == "production"

# ---------------------------------------------------------------------------
# Database bootstrap
# ---------------------------------------------------------------------------


async def init_session_db() -> None:
    """Create the data/ directory and sessions table if they do not exist."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                data       TEXT NOT NULL DEFAULT '{}',
                expires_at TIMESTAMP NOT NULL
            )
        """)
        await db.commit()
    logger.debug("Session DB ready at %s", _DB_PATH)


async def cleanup_expired_sessions() -> None:
    """Delete expired sessions from the database (call periodically)."""
    now = datetime.now(UTC).isoformat()
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM sessions WHERE expires_at < ?", (now,)
        )
        await db.commit()
        if cursor.rowcount:
            logger.debug("Purged %d expired sessions", cursor.rowcount)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


async def _load_session(session_id: str) -> dict | None:
    """Return the session data dict, or None if missing / expired."""
    now = datetime.now(UTC).isoformat()
    async with aiosqlite.connect(_DB_PATH) as db:
        async with db.execute(
            "SELECT data FROM sessions WHERE session_id = ? AND expires_at > ?",
            (session_id, now),
        ) as cursor:
            row = await cursor.fetchone()
    if row is None:
        return None
    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        logger.warning("Corrupt session data for session_id=%s — resetting", session_id)
        return {}


async def _save_session(session_id: str, data: dict) -> None:
    """Upsert a session row with a refreshed expiry."""
    expires_at = (datetime.now(UTC) + timedelta(days=_SESSION_TTL_DAYS)).isoformat()
    payload = json.dumps(data, default=str)
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO sessions (session_id, data, expires_at)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                data       = excluded.data,
                expires_at = excluded.expires_at
            """,
            (session_id, payload, expires_at),
        )
        await db.commit()


async def _delete_session(session_id: str) -> None:
    """Remove a session row entirely."""
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await db.commit()


# ---------------------------------------------------------------------------
# Helper available to route handlers
# ---------------------------------------------------------------------------


async def destroy_session(request: Request, response: Response) -> None:
    """Delete the server-side session and clear the session cookie.

    Call this from logout or account-delete handlers after you have obtained
    the response object.  Clears request.state.session in place.
    """
    session_id = request.cookies.get(_COOKIE_NAME)
    if session_id:
        await _delete_session(session_id)
    request.state.session.clear()
    request.state._session_destroyed = True
    response.delete_cookie(_COOKIE_NAME)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class SQLiteSessionMiddleware(BaseHTTPMiddleware):
    """Server-side session middleware backed by SQLite.

    Attaches ``request.state.session`` (a plain dict) to every request.
    Writes back to SQLite after the response only when the session was
    modified — checked by comparing a snapshot taken before the handler runs.
    """

    async def dispatch(self, request: Request, call_next):
        # ── Load session ────────────────────────────────────────────────────
        session_id = request.cookies.get(_COOKIE_NAME)
        existing_data: dict | None = None

        if session_id:
            existing_data = await _load_session(session_id)

        if existing_data is None:
            # New session — generate a fresh ID
            session_id = uuid.uuid4().hex
            existing_data = {}

        # Snapshot for dirty detection (shallow copy is sufficient for top-level keys)
        snapshot = dict(existing_data)

        # Attach to request state
        request.state.session = existing_data
        request.state._session_destroyed = False

        # Expose session_id to logging context before the request is handled
        session_id_var.set(session_id)

        # ── Handle request ──────────────────────────────────────────────────
        response = await call_next(request)

        # ── Persist if changed ──────────────────────────────────────────────
        if request.state._session_destroyed:
            # destroy_session() already deleted the row and cleared the dict
            response.delete_cookie(_COOKIE_NAME)
            return response

        current_data = request.state.session
        session_is_dirty = current_data != snapshot

        if session_is_dirty:
            await _save_session(session_id, current_data)

        # Don't set Set-Cookie on publicly cacheable responses (e.g. blog
        # pages) unless the session was modified — browsers refuse to cache
        # responses that carry Set-Cookie.
        cache_control = response.headers.get("cache-control", "")
        if "public" in cache_control and not session_is_dirty:
            return response

        cookie_kwargs = dict(
            key=_COOKIE_NAME,
            value=session_id,
            httponly=True,
            samesite="lax",
            max_age=_SESSION_TTL_DAYS * 86_400,
            path="/",
        )
        if _IS_PRODUCTION:
            cookie_kwargs["secure"] = True

        response.set_cookie(**cookie_kwargs)
        return response
