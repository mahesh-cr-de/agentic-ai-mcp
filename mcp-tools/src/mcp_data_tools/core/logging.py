"""Structured (JSON) logging configuration.

The rest of the codebase never calls :func:`logging.basicConfig` directly;
it obtains loggers through :func:`get_logger` so that every log record —
whether emitted from a tool handler, an adapter, or the audit engine — is
serialized consistently and can be shipped to a log aggregator (Cloud
Logging, ELK, etc.) without a separate parsing step.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, ClassVar

_CONFIGURED = False

_LEVEL_NAMES: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects.

    Any keyword arguments passed via ``logger.info(msg, extra={...})`` are
    merged into the top-level JSON object, so structured fields (e.g.
    ``tool_name``, ``request_id``) survive alongside the free-text message.
    """

    _RESERVED: ClassVar[frozenset[str]] = frozenset(
        logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
    ) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        """Render a log record as a JSON string.

        Args:
            record: The record emitted by the logging framework.

        Returns:
            A single-line JSON document.
        """
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in self._RESERVED:
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", *, force: bool = False) -> None:
    """Configure the root logger to emit structured JSON to stdout.

    Args:
        level: One of ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, ``CRITICAL``.
        force: Reconfigure even if :func:`configure_logging` was already
            called once in this process. Primarily useful in tests.

    Raises:
        ValueError: If ``level`` is not a recognized logging level name.

    Example:
        >>> configure_logging("DEBUG")
        >>> get_logger(__name__).debug("ready")
    """
    global _CONFIGURED  # noqa: PLW0603 - module-level "has logging been configured" flag is the simplest correct idiom here
    if _CONFIGURED and not force:
        return

    normalized = level.upper()
    if normalized not in _LEVEL_NAMES:
        raise ValueError(f"Unknown log level {level!r}; expected one of {sorted(_LEVEL_NAMES)}")

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(_LEVEL_NAMES[normalized])
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger, configuring logging on first use.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A standard library :class:`logging.Logger` that emits JSON lines.
    """
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
