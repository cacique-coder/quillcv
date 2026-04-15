"""Centralized Jinja2Templates instance for all routes."""

import sys
from pathlib import Path

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class _CompatTemplates(Jinja2Templates):
    """Wrapper that accepts both old and new Starlette TemplateResponse signatures.

    Starlette <1.0:  TemplateResponse(name, {"request": request, ...})
    Starlette  1.0:  TemplateResponse(request, name, context)

    This shim detects the old-style call and reorders the arguments.
    Remove once all call sites are migrated to the new signature.
    """

    def TemplateResponse(self, *args, **kwargs):  # noqa: N802
        # Old style: first arg is a string (template name), second is context dict
        if args and isinstance(args[0], str):
            name = args[0]
            context = args[1] if len(args) > 1 else kwargs.get("context", {})
            request = context.pop("request", None) if isinstance(context, dict) else None
            if request is None:
                request = kwargs.get("request")
            remaining_args = args[2:]
            return super().TemplateResponse(request, name, context, *remaining_args, **kwargs)
        # New style: first arg is request — pass through
        return super().TemplateResponse(*args, **kwargs)


templates = _CompatTemplates(directory=TEMPLATES_DIR)

# Workaround for Jinja2 3.1.6 + Python 3.14 — the LRU cache uses tuples
# containing dicts as keys, which became unhashable in 3.14.
# cache_size=0 at Environment init time disables caching.
# Remove once Jinja2 ships a fix.
if sys.version_info >= (3, 14):
    from jinja2 import Environment, FileSystemLoader

    templates.env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
        cache_size=0,
    )
