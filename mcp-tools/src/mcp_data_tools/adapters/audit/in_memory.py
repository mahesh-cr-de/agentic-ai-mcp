"""In-memory audit sink used by tests and interactive examples."""

from __future__ import annotations

import threading
from collections import deque

from mcp_data_tools.ports.interfaces import AuditSinkPort
from mcp_data_tools.ports.models import AuditEvent


class InMemoryAuditSink(AuditSinkPort):
    """Keeps audit events in a bounded in-process deque.

    Attributes:
        max_events: Oldest events are dropped once this many are stored.
    """

    def __init__(self, max_events: int = 1000) -> None:
        self.max_events = max_events
        self._events: deque[AuditEvent] = deque(maxlen=max_events)
        self._lock = threading.Lock()

    def write(self, event: AuditEvent) -> None:
        """Store the event in memory.

        Args:
            event: The event to persist.
        """
        with self._lock:
            self._events.append(event)

    def read_recent(self, limit: int = 100) -> tuple[AuditEvent, ...]:
        """Return the most recent events, newest first.

        Args:
            limit: Maximum number of events to return.

        Returns:
            A tuple of :class:`AuditEvent`.
        """
        with self._lock:
            ordered = list(self._events)[::-1]
        return tuple(ordered[:limit])


__all__ = ["InMemoryAuditSink"]
