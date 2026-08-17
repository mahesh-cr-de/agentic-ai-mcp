"""Immutable domain models shared across ports and adapters.

These dataclasses are the vocabulary the rest of the system speaks in, so
that a BigQuery-specific response object never leaks past the adapter
boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


@dataclass(frozen=True, slots=True)
class QueryCostEstimate:
    """Result of a dry-run cost estimate for a SQL query.

    Attributes:
        estimated_bytes_processed: Bytes the query would scan if executed.
        estimated_cost_usd: Approximate on-demand cost in US dollars.
            ``None`` when the backend does not expose pricing (e.g. a flat
            reservation) and only byte counts are meaningful.
        referenced_tables: Fully-qualified ``project.dataset.table`` names
            the query would read from.
    """

    estimated_bytes_processed: int
    estimated_cost_usd: float | None
    referenced_tables: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Result of executing a (guardrail-approved) query.

    Attributes:
        rows: Result rows as plain dictionaries, already truncated to the
            guardrail's ``max_rows_returned`` ceiling.
        total_rows_in_result_set: Total row count the backend reports,
            which may exceed ``len(rows)`` if the result was truncated.
        bytes_processed: Actual bytes scanned by the query.
        job_id: Backend-specific job identifier, for traceability in the
            audit log and in the backend's own console.
    """

    rows: tuple[dict[str, Any], ...]
    total_rows_in_result_set: int
    bytes_processed: int
    job_id: str


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    """Metadata describing a single object-storage blob.

    Attributes:
        bucket: Bucket (or container) name.
        name: Object key/path within the bucket.
        size_bytes: Object size in bytes.
        content_type: MIME type, if known.
        updated_at: Last-modified timestamp, if known.
        etag: Backend-provided integrity/version tag.
    """

    bucket: str
    name: str
    size_bytes: int
    content_type: str | None
    updated_at: datetime | None
    etag: str | None = None


class DagRunState(StrEnum):
    """Normalized DAG-run lifecycle state across orchestrators."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DagRunStatus:
    """Status of a single orchestrated DAG/workflow run.

    Attributes:
        dag_id: Identifier of the DAG/workflow definition.
        run_id: Identifier of this specific run.
        state: Normalized lifecycle state.
        start_date: When the run began, if it has started.
        end_date: When the run finished, if it has finished.
    """

    dag_id: str
    run_id: str
    state: DagRunState
    start_date: datetime | None
    end_date: datetime | None


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """A single, immutable record of a governed tool invocation.

    Attributes:
        event_id: Unique identifier for this event (e.g. a UUID4).
        timestamp: When the decision was made.
        tool_name: MCP tool that was invoked.
        actor: Best-effort identifier of the calling agent/session.
        parameters: Redacted/normalized input parameters.
        decision: ``"allowed"`` or ``"denied"``.
        reason: Human-readable explanation of the decision.
        backend_job_id: Downstream job/run id, if the operation executed.
    """

    event_id: str
    timestamp: datetime
    tool_name: str
    actor: str
    parameters: dict[str, Any]
    decision: str
    reason: str
    backend_job_id: str | None = None


__all__ = [
    "AuditEvent",
    "DagRunState",
    "DagRunStatus",
    "ObjectMetadata",
    "QueryCostEstimate",
    "QueryResult",
]
