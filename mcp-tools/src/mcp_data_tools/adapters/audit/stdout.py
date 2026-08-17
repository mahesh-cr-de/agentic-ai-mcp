"""Stdout audit sink — writes events as structured log lines.

Useful in containerized deployments where a log-shipping sidecar (Fluent
Bit, the Cloud Logging agent, etc.) already collects stdout and forwards
it to a central store; avoids managing a separate audit file.
"""

from __future__ import annotations

from dataclasses import asdict

from mcp_data_tools.core.logging import get_logger
from mcp_data_tools.ports.interfaces import AuditSinkPort
from mcp_data_tools.ports.models import AuditEvent

_LOGGER = get_logger("mcp_data_tools.audit")


class StdoutAuditSink(AuditSinkPort):
    """Emits each audit event as a structured log record.

    Note:
        :meth:`read_recent` always returns an empty tuple: stdout is a
        write-only sink by design. Use :class:`LocalJsonlAuditSink` or a
        queryable backend if the "list recent audit events" tool is
        needed.
    """

    def write(self, event: AuditEvent) -> None:
        """Log the event at INFO level with full structured fields.

        Args:
            event: The event to persist.
        """
        _LOGGER.info("audit_event", extra={"audit": asdict(event)})

    def read_recent(self, limit: int = 100) -> tuple[AuditEvent, ...]:
        """Return an empty tuple; stdout audit events are not queryable.

        Args:
            limit: Ignored.

        Returns:
            Always ``()``.
        """
        return ()


__all__ = ["StdoutAuditSink"]
