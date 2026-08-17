"""Abstract port interfaces (hexagonal architecture boundary).

Concrete implementations live under ``mcp_data_tools.adapters``. Each port
has a "real" adapter (talks to an actual cloud service) and an in-memory
mock adapter used throughout the test suite and in the ``examples/``
walkthroughs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from mcp_data_tools.ports.models import (
    AuditEvent,
    DagRunStatus,
    ObjectMetadata,
    QueryCostEstimate,
    QueryResult,
)


class QueryEnginePort(ABC):
    """Boundary for SQL query engines (BigQuery, Databricks SQL, etc.)."""

    @abstractmethod
    def estimate_cost(self, sql: str) -> QueryCostEstimate:
        """Perform a dry run and return the projected cost/scan size.

        Args:
            sql: The SQL statement to estimate.

        Returns:
            A :class:`QueryCostEstimate` describing the dry-run outcome.

        Raises:
            mcp_data_tools.core.exceptions.BackendOperationError: If the
                dry run itself fails (e.g. invalid SQL).
        """

    @abstractmethod
    def execute(self, sql: str, *, max_bytes_billed: int, row_limit: int) -> QueryResult:
        """Execute a SQL statement under an enforced cost/row ceiling.

        Args:
            sql: The SQL statement to execute. Callers are responsible for
                guardrail checks (read-only enforcement, table allow-list)
                *before* calling this method — the adapter only enforces
                the billing/row ceilings it is physically able to enforce.
            max_bytes_billed: Hard cap passed to the backend; the backend
                must abort rather than exceed this.
            row_limit: Maximum number of rows to materialize into the
                returned :class:`QueryResult`.

        Returns:
            A :class:`QueryResult`.

        Raises:
            mcp_data_tools.core.exceptions.BackendOperationError: If
                execution fails or exceeds ``max_bytes_billed``.
        """


class ObjectStoragePort(ABC):
    """Boundary for blob/object storage (GCS, ADLS Gen2, S3, etc.)."""

    @abstractmethod
    def get_object_metadata(self, bucket: str, name: str) -> ObjectMetadata:
        """Fetch metadata for a single object without downloading its body.

        Args:
            bucket: Bucket/container name.
            name: Object key/path.

        Returns:
            An :class:`ObjectMetadata` instance.

        Raises:
            mcp_data_tools.core.exceptions.BackendOperationError: If the
                object does not exist or the backend call fails.
        """

    @abstractmethod
    def list_objects(
        self, bucket: str, *, prefix: str = "", max_results: int = 100
    ) -> tuple[ObjectMetadata, ...]:
        """List objects under a prefix.

        Args:
            bucket: Bucket/container name.
            prefix: Key prefix to filter by.
            max_results: Maximum number of objects to return.

        Returns:
            A tuple of :class:`ObjectMetadata`, at most ``max_results`` long.
        """


class OrchestratorPort(ABC):
    """Boundary for workflow orchestrators (Airflow, Cloud Composer, Dagster, etc.)."""

    @abstractmethod
    def trigger_dag_run(self, dag_id: str, *, conf: dict[str, Any] | None = None) -> DagRunStatus:
        """Trigger a new run of a DAG/workflow.

        Args:
            dag_id: Identifier of the DAG/workflow to trigger.
            conf: Optional run-time configuration payload passed to the DAG.

        Returns:
            The initial :class:`DagRunStatus` (typically ``queued``).

        Raises:
            mcp_data_tools.core.exceptions.BackendOperationError: If the
                trigger request fails.
        """

    @abstractmethod
    def get_dag_run_status(self, dag_id: str, run_id: str) -> DagRunStatus:
        """Fetch the current status of a previously triggered run.

        Args:
            dag_id: Identifier of the DAG/workflow.
            run_id: Identifier of the specific run.

        Returns:
            The current :class:`DagRunStatus`.

        Raises:
            mcp_data_tools.core.exceptions.BackendOperationError: If the
                run cannot be found or the backend call fails.
        """


class AuditSinkPort(ABC):
    """Boundary for the append-only audit trail."""

    @abstractmethod
    def write(self, event: AuditEvent) -> None:
        """Persist a single audit event.

        Args:
            event: The event to persist.

        Raises:
            mcp_data_tools.core.exceptions.AuditWriteError: If the event
                cannot be durably written.
        """

    @abstractmethod
    def read_recent(self, limit: int = 100) -> tuple[AuditEvent, ...]:
        """Return the most recent audit events, newest first.

        Args:
            limit: Maximum number of events to return.

        Returns:
            A tuple of :class:`AuditEvent`, at most ``limit`` long.
        """


__all__ = [
    "AuditSinkPort",
    "ObjectStoragePort",
    "OrchestratorPort",
    "QueryEnginePort",
]
