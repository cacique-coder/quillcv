"""Logging configuration for QuillCV.

Call setup_logging(dev_mode) once at application startup, before creating
the FastAPI app instance.
"""

import logging
import logging.config


# ---------------------------------------------------------------------------
# Logfmt formatter (key=value, used for both dev and prod)
# ---------------------------------------------------------------------------

_STANDARD_ATTRS = logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()


class _LogfmtFormatter(logging.Formatter):
    """Single logfmt (key=value) formatter for both dev and prod."""

    def format(self, record: logging.LogRecord) -> str:
        from datetime import datetime, timezone

        from app.infrastructure.middleware.main import client_ip_var, request_id_var, session_id_var, user_id_var

        timestamp = (
            datetime.fromtimestamp(record.created, tz=timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        level = record.levelname
        request_id = request_id_var.get("-")
        session_id = session_id_var.get("-")
        user_id = user_id_var.get("-")
        ip = client_ip_var.get("-")

        # Collect extra fields passed via extra= kwarg
        extra: dict = {}
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                extra[key] = value

        parts = [
            f"timestamp={timestamp}",
            f"level={level}",
        ]

        # For request logs the caller passes method/path/status/duration_ms
        # via extra and uses "request" as the message — render as a flat line.
        # For all other logs include the logger name and msg.
        if extra:
            for key, value in extra.items():
                parts.append(f"{key}={value}")
        else:
            name = record.name.removeprefix("app.")
            parts.append(f"logger={name}")

        if request_id != "-":
            parts.append(f"request_id={request_id}")
        if session_id != "-":
            parts.append(f"session_id={session_id}")
        if user_id != "-":
            parts.append(f"user_id={user_id}")
        if ip != "-":
            parts.append(f"ip={ip}")

        # Only add msg when it is not the bare "request" sentinel used by
        # RequestLoggingMiddleware (that log line is fully described by its
        # extra fields).
        msg = record.getMessage()
        if msg and msg != "request":
            quoted = f'"{msg}"' if " " in msg else msg
            parts.append(f"msg={quoted}")

        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            parts.append(f'exc="{exc_text}"')

        return " ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup_logging(dev_mode: bool) -> None:
    """Configure the root logger and per-package levels.

    Must be called before the FastAPI app is constructed so that all
    subsequent logger.getLogger(__name__) calls inherit the configuration.

    Args:
        dev_mode: When True, use DEBUG level + stdout.
                  When False, use INFO level + stderr.
    """
    app_level = "DEBUG" if dev_mode else "INFO"
    third_party_level = "INFO" if dev_mode else "WARNING"

    stream = "ext://sys.stdout" if dev_mode else "ext://sys.stderr"

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "main": {
                "()": "app.logging_config._LogfmtFormatter",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": stream,
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
            "sqlalchemy.engine": {
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
