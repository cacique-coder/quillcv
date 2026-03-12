"""Logging configuration for QuillCV.

Call setup_logging(dev_mode) once at application startup, before creating
the FastAPI app instance.
"""

import logging
import logging.config


# ---------------------------------------------------------------------------
# ANSI colour helpers (no external dependencies)
# ---------------------------------------------------------------------------

_RESET = "\033[0m"
_COLOURS = {
    "DEBUG":    "\033[36m",   # cyan
    "INFO":     "\033[32m",   # green
    "WARNING":  "\033[33m",   # yellow
    "ERROR":    "\033[31m",   # red
    "CRITICAL": "\033[35m",   # magenta
}


class _ColourFormatter(logging.Formatter):
    """Human-readable, coloured formatter for development output."""

    _FMT = "%(asctime)s %(levelname)-5s [%(name)s] %(message)s"
    _DATE_FMT = "%H:%M:%S"

    def format(self, record: logging.LogRecord) -> str:
        colour = _COLOURS.get(record.levelname, "")
        level_str = f"{colour}{record.levelname:<5}{_RESET}"
        # Shorten logger names: app.routers.cv -> app.routers.cv (already short)
        # but trim the app. prefix to save horizontal space in the terminal
        name = record.name.removeprefix("app.")
        formatted = (
            f"{self.formatTime(record, self._DATE_FMT)} "
            f"{level_str} "
            f"[{name}] "
            f"{record.getMessage()}"
        )
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        return formatted


class _JSONFormatter(logging.Formatter):
    """Structured JSON formatter suitable for log aggregators (prod)."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
                         .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Merge in any extra structured fields the caller passed via the
        # `extra=` kwarg (anything that isn't a standard LogRecord attribute).
        _STANDARD_ATTRS = logging.LogRecord(
            "", 0, "", 0, "", (), None
        ).__dict__.keys()
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup_logging(dev_mode: bool) -> None:
    """Configure the root logger and per-package levels.

    Must be called before the FastAPI app is constructed so that all
    subsequent logger.getLogger(__name__) calls inherit the configuration.

    Args:
        dev_mode: When True, use DEBUG level + colour output.
                  When False, use INFO level + JSON output.
    """
    app_level = "DEBUG" if dev_mode else "INFO"
    third_party_level = "INFO" if dev_mode else "WARNING"

    formatter_class = (
        "app.logging_config._ColourFormatter"
        if dev_mode
        else "app.logging_config._JSONFormatter"
    )

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "main": {
                "()": formatter_class,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "main",
            },
        },
        "loggers": {
            # Our application code
            "app": {
                "level": app_level,
                "handlers": ["console"],
                "propagate": False,
            },
            # Silence noisy third-party libraries
            "uvicorn.access": {
                "level": "WARNING",   # we have our own request middleware
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn": {
                "level": third_party_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "fastapi": {
                "level": third_party_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "httpx": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
            "anthropic": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
        },
        # Root catches everything else (sqlalchemy, aiofiles, etc.)
        "root": {
            "level": third_party_level,
            "handlers": ["console"],
        },
    })
