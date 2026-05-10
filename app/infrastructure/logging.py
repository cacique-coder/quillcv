"""Logging configuration for QuillCV.

Call setup_logging(dev_mode) once at application startup, before creating
the FastAPI app instance.
"""

import logging
import logging.config
import logging.handlers
import sys
from datetime import UTC
from pathlib import Path

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_STANDARD_ATTRS = logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()

# ---------------------------------------------------------------------------
# Pretty dev formatter (colorized, human-readable)
# ---------------------------------------------------------------------------

_LEVEL_COLORS = {
    "DEBUG":    "\033[36m",       # cyan
    "INFO":     "\033[32m",       # green
    "WARNING":  "\033[33m",       # yellow
    "ERROR":    "\033[31m",       # red
    "CRITICAL": "\033[1;31m",     # red bold
}
_DIM   = "\033[2m"
_RESET = "\033[0m"


class _PrettyDevFormatter(logging.Formatter):
    """Colorized, human-readable formatter for local development."""

    def __init__(self) -> None:
        super().__init__()
        self._tty = sys.stdout.isatty()

    def _c(self, code: str, text: str) -> str:
        return f"{code}{text}{_RESET}" if self._tty else text

    def format(self, record: logging.LogRecord) -> str:
        from datetime import datetime

        from app.infrastructure.middleware.main import (
            client_ip_var,
            request_id_var,
            session_id_var,
            user_id_var,
        )

        ts = datetime.fromtimestamp(record.created, tz=UTC).strftime("%H:%M:%S.") + \
            f"{record.msecs:03.0f}"
        level_color = _LEVEL_COLORS.get(record.levelname, "")
        level_str   = self._c(level_color, f"{record.levelname:<8}")
        ts_str      = self._c(_DIM, ts)
        name_str    = self._c(_DIM, record.name.removeprefix("app."))

        msg = record.getMessage()
        is_request_sentinel = msg == "request"

        # Collect caller-supplied extras
        extra: dict = {}
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                extra[key] = value

        # Context vars
        ctx: dict = {}
        for var, key in (
            (request_id_var, "request_id"),
            (session_id_var, "session_id"),
            (user_id_var,    "user_id"),
            (client_ip_var,  "ip"),
        ):
            val = var.get("-")
            if val != "-":
                ctx[key] = val

        kv_parts = [f"{k}={v}" for k, v in {**extra, **ctx}.items()]
        kv_str   = self._c(_DIM, "  " + "  ".join(kv_parts)) if kv_parts else ""

        if is_request_sentinel:
            line = f"{ts_str}  {level_str}  {name_str}{kv_str}"
        else:
            line = f"{ts_str}  {level_str}  {name_str}  {msg}{kv_str}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)

        return line


class _LogfmtFormatter(logging.Formatter):
    """Logfmt (key=value) formatter for prod log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        from datetime import datetime

        from app.infrastructure.middleware.main import client_ip_var, request_id_var, session_id_var, user_id_var

        timestamp = (
            datetime.fromtimestamp(record.created, tz=UTC)
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

    if dev_mode:
        Path("tmp").mkdir(parents=True, exist_ok=True)
        formatters = {
            "pretty": {"()": "app.infrastructure.logging._PrettyDevFormatter"},
            "logfmt": {"()": "app.infrastructure.logging._LogfmtFormatter"},
        }
        handlers: dict = {
            "console": {
                "class": "logging.StreamHandler",
                "stream": stream,
                "formatter": "pretty",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "tmp/dev.log",
                "maxBytes": 10_000_000,
                "backupCount": 3,
                "formatter": "logfmt",
            },
        }
        active_handlers = ["console", "file"]
    else:
        formatters = {
            "logfmt": {"()": "app.infrastructure.logging._LogfmtFormatter"},
        }
        handlers = {
            "console": {
                "class": "logging.StreamHandler",
                "stream": stream,
                "formatter": "logfmt",
            },
        }
        active_handlers = ["console"]

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": handlers,
        "loggers": {
            # Our application code
            "app": {
                "level": app_level,
                "handlers": active_handlers,
                "propagate": False,
            },
            # Silence noisy third-party libraries
            "uvicorn.access": {
                "level": "WARNING",   # we have our own request middleware
                "handlers": active_handlers,
                "propagate": False,
            },
            "uvicorn": {
                "level": third_party_level,
                "handlers": active_handlers,
                "propagate": False,
            },
            "fastapi": {
                "level": third_party_level,
                "handlers": active_handlers,
                "propagate": False,
            },
            "httpx": {
                "level": "WARNING",
                "handlers": active_handlers,
                "propagate": False,
            },
            "anthropic": {
                "level": "WARNING",
                "handlers": active_handlers,
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "WARNING",
                "handlers": active_handlers,
                "propagate": False,
            },
        },
        # Root catches everything else (sqlalchemy, aiofiles, etc.)
        "root": {
            "level": third_party_level,
            "handlers": active_handlers,
        },
    })
