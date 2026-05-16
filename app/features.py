"""Feature flag registry + cached reads.

Flags are declared in ``REGISTRY`` with a default callable (often env-driven).
At runtime, a row in ``feature_flags`` overrides the default for a given key.
The cache is loaded once on app startup and refreshed on admin toggle, so
hot-path reads stay synchronous and DB-free.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select

from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.orm_models import FeatureFlag

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FlagSpec:
    key: str
    label: str
    description: str
    default: Callable[[], bool]


def _open_signups_default() -> bool:
    """Env-driven default for the open-signups flag."""
    raw = os.environ.get("OPEN_SIGNUPS_ENABLED")
    if raw is not None:
        return raw.lower() in {"1", "true", "yes", "on"}
    return os.environ.get("APP_ENV", "development") != "production"


REGISTRY: dict[str, FlagSpec] = {
    "open_signups": FlagSpec(
        key="open_signups",
        label="Open signups",
        description=(
            "When on, the public /signup form creates new accounts. When off, "
            "it captures Expressions of Interest instead, and OAuth blocks new "
            "users. Invited signups always work regardless of this flag."
        ),
        default=_open_signups_default,
    ),
}


_cache: dict[str, bool] = {}
_cache_loaded = False


def is_enabled(key: str) -> bool:
    """Sync read — returns the DB override if cached, else the registry default."""
    spec = REGISTRY.get(key)
    if spec is None:
        return False
    if key in _cache:
        return _cache[key]
    return spec.default()


async def refresh_cache() -> None:
    """Load every flag row into the in-memory cache. Call at startup."""
    global _cache_loaded
    async with async_session() as db:
        rows = await db.execute(select(FeatureFlag))
        flags = rows.scalars().all()
    _cache.clear()
    for f in flags:
        _cache[f.key] = f.enabled
    _cache_loaded = True
    logger.info("Feature flag cache loaded (%d overrides)", len(_cache))


async def set_flag(key: str, enabled: bool, updated_by: str | None = None) -> None:
    """Persist an override and update the cache. Unknown keys raise KeyError."""
    if key not in REGISTRY:
        raise KeyError(f"Unknown feature flag: {key}")
    async with async_session() as db:
        row = await db.execute(select(FeatureFlag).where(FeatureFlag.key == key))
        flag = row.scalar_one_or_none()
        if flag is None:
            flag = FeatureFlag(key=key, enabled=enabled, updated_by=updated_by)
            db.add(flag)
        else:
            flag.enabled = enabled
            flag.updated_by = updated_by
        await db.commit()
    _cache[key] = enabled


async def list_flags() -> list[dict]:
    """Return one entry per registered flag with its effective + default state."""
    async with async_session() as db:
        rows = await db.execute(select(FeatureFlag))
        flags = {f.key: f for f in rows.scalars().all()}
    out: list[dict] = []
    for spec in REGISTRY.values():
        override = flags.get(spec.key)
        default = spec.default()
        effective = override.enabled if override is not None else default
        out.append({
            "key": spec.key,
            "label": spec.label,
            "description": spec.description,
            "default": default,
            "override": override.enabled if override else None,
            "enabled": effective,
            "updated_at": override.updated_at if override else None,
            "updated_by": override.updated_by if override else None,
        })
    return out
