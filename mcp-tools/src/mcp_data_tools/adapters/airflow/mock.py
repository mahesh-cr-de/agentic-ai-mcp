"""In-memory :class:`OrchestratorPort` used by unit tests and examples."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from typing import Any

from mcp_data_tools.core.exceptions import BackendOperationError
from mcp_data_tools.ports.interfaces import OrchestratorPort
from mcp_data_tools.ports.models import DagRunState, DagRunStatus


class InMemoryOrchestrator(OrchestratorPort):
    """A fake orchestrator that immediately "runs" any known DAG id.

    Attributes:
        known_dag_ids: DAG ids that may be triggered; triggering an
            unknown id raises :class:`BackendOperationError`, mirroring a
            real Airflow 404.

    Example:
        >>> orch = InMemoryOrchestrator(known_dag_ids={"ingest_orders"})
        >>> status = orch.trigger_dag_run("ingest_orders")
        >>> status.state.value
        'success'
        >>> orch.get_dag_run_status("ingest_orders", status.run_id).state.value
        'success'
    """

    def __init__(self, known_dag_ids: set[str] | None = None) -> None:
        self.known_dag_ids = known_dag_ids or set()
        self._runs: dict[tuple[str, str], DagRunStatus] = {}
        self._counter = itertools.count(1)

    def trigger_dag_run(self, dag_id: str, *, conf: dict[str, Any] | None = None) -> DagRunStatus:
        """Simulate triggering a DAG run, resolving to ``success`` instantly.

        Args:
            dag_id: Identifier of the DAG to trigger.
            conf: Ignored by the mock beyond being accepted.

        Returns:
            A :class:`DagRunStatus` in the ``success`` state.

        Raises:
            BackendOperationError: If ``dag_id`` is not in
                ``known_dag_ids``.
        """
        if dag_id not in self.known_dag_ids:
            raise BackendOperationError(f"Unknown DAG id: {dag_id}")
        run_id = f"mock_run_{next(self._counter)}"
        now = datetime.now(UTC)
        status = DagRunStatus(
            dag_id=dag_id,
            run_id=run_id,
            state=DagRunState.SUCCESS,
            start_date=now,
            end_date=now,
        )
        self._runs[(dag_id, run_id)] = status
        return status

    def get_dag_run_status(self, dag_id: str, run_id: str) -> DagRunStatus:
        """Look up a previously triggered run.

        Args:
            dag_id: Identifier of the DAG.
            run_id: Identifier of the specific run.

        Returns:
            The stored :class:`DagRunStatus`.

        Raises:
            BackendOperationError: If the run is unknown.
        """
        key = (dag_id, run_id)
        if key not in self._runs:
            raise BackendOperationError(f"Unknown DAG run: {dag_id}/{run_id}")
        return self._runs[key]


__all__ = ["InMemoryOrchestrator"]
