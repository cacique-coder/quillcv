"""Application settings.

Database config is assembled from individual env vars so the same
configuration shape works in development, test, container, and production:

    DB_HOST       hostname (default: ``localhost`` for dev/test, ``db`` inside compose)
    DB_PORT       port (default: 5432)
    DB_USER       user (default: postgres)
    DB_PASSWORD   password (default: postgres)
    DB_NAME       database name (default: quillcv_dev or quillcv_test)
    DB_DRIVER     SQLAlchemy driver (default: postgresql+asyncpg)

A full ``DATABASE_URL`` env var (Heroku/Render/Rails-style) still wins if
set — it's the production override for managed Postgres providers.
"""

import os

APP_ENV = os.environ.get("APP_ENV", "development")

_DEFAULT_DB_NAMES = {
    "development": "quillcv_dev",
    "test": "quillcv_test",
    "production": "quillcv_prod",
}

_POOL_SIZE = {"development": 5, "test": 5, "production": 10}


def _build_database_url() -> str:
    driver = os.environ.get("DB_DRIVER", "postgresql+asyncpg")
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "postgres")
    name = os.environ.get("DB_NAME", _DEFAULT_DB_NAMES.get(APP_ENV, "quillcv_dev"))
    return f"{driver}://{user}:{password}@{host}:{port}/{name}"


def database_config() -> dict:
    """Return database config for the current environment.

    Resolution order: ``DATABASE_URL`` (full override) → assembled from
    ``DB_*`` parts → built-in defaults.
    """
    return {
        "url": os.environ.get("DATABASE_URL") or _build_database_url(),
        "echo": False,
        "pool_size": _POOL_SIZE.get(APP_ENV, 5),
    }


def open_signups_enabled() -> bool:
    """Whether the public /signup form may create new accounts.

    When False, the open-signup branch (no invite code) records an
    Expression of Interest instead of creating an account, and OAuth
    callbacks reject new users (existing users can still sign in).
    Invited signups always work regardless of this flag.

    Default: True in development/test, False in production unless the
    operator explicitly sets ``OPEN_SIGNUPS_ENABLED=true``.
    """
    raw = os.environ.get("OPEN_SIGNUPS_ENABLED")
    if raw is not None:
        return raw.lower() in {"1", "true", "yes", "on"}
    return APP_ENV != "production"
