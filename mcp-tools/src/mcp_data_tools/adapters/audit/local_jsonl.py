"""Local append-only JSON Lines audit sink.

The default sink for local development and single-node deployments. Each
:class:`~mcp_data_tools.ports.models.AuditEvent` is appended as one JSON
object per line, using an ``O_APPEND`` write so concurrent writers cannot
truncate or interleave-corrupt each other's records on POSIX filesystems.
"""

from __future__ import annotations

import json
import os
import threading
from collections import deque
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from mcp_data_tools.core.exceptions import AuditWriteError
from mcp_data_tools.core.logging import get_logger
from mcp_data_tools.ports.interfaces import AuditSinkPort
from mcp_data_tools.ports.models import AuditEvent

_LOGGER = get_logger(__name__)


def _default_json(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class LocalJsonlAuditSink(AuditSinkPort):
    """Appends audit events to a local ``.jsonl`` file.

    Attributes:
        path: Filesystem path the sink writes to. Parent directories are
            created on first write.

    Example:
        >>> import tempfile, os
        >>> from mcp_data_tools.ports.models import AuditEvent
        >>> from datetime import datetime, timezone
        >>> tmp = os.path.join(tempfile.mkdtemp(), "audit.jsonl")
        >>> sink = LocalJsonlAuditSink(tmp)
        >>> sink.write(AuditEvent(
        ...     event_id="e1", timestamp=datetime.now(timezone.utc),
        ...     tool_name="t", actor="a", parameters={}, decision="allowed",
        ...     reason="ok",
        ... ))
        >>> len(sink.read_recent())
        1
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def write(self, event: AuditEvent) -> None:
        """Append one audit event as a JSON line.

        Args:
            event: The event to persist.

        Raises:
            AuditWriteError: If the file cannot be written to.
        """
        payload = asdict(event)
        line = json.dumps(payload, default=_default_json)
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(str(self.path), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
                try:
                    os.write(fd, (line + "\n").encode("utf-8"))
                finally:
                    os.close(fd)
        except OSError as exc:
            raise AuditWriteError(f"Failed to write audit event to {self.path}: {exc}") from exc

    def read_recent(self, limit: int = 100) -> tuple[AuditEvent, ...]:
        """Return the most recently written events, newest first.

        Args:
            limit: Maximum number of events to return.

        Returns:
            A tuple of :class:`AuditEvent`.
        """
        if not self.path.exists():
            return ()

        recent_lines: deque[str] = deque(maxlen=limit)
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    recent_lines.append(stripped)

        events = [self._deserialize(line) for line in recent_lines]
        events.reverse()
        return tuple(events)

    @staticmethod
    def _deserialize(line: str) -> AuditEvent:
        data = json.loads(line)
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return AuditEvent(**data)


__all__ = ["LocalJsonlAuditSink"]
