"""Real Airflow adapter, backed by the Airflow stable REST API (v1) over HTTP.

Works against both self-managed Apache Airflow and Google Cloud Composer's
Airflow web server (the API surface is the same). Uses ``httpx`` rather
than a heavier Airflow-specific client library to keep the dependency
footprint small and the HTTP behavior fully explicit and testable.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx

from mcp_data_tools.core.exceptions import (
    BackendConnectionError,
    BackendOperationError,
    RetryExhaustedError,
)
from mcp_data_tools.core.logging import get_logger
from mcp_data_tools.core.retry import RetryPolicy, with_retry
from mcp_data_tools.ports.interfaces import OrchestratorPort
from mcp_data_tools.ports.models import DagRunState, DagRunStatus

_LOGGER = get_logger(__name__)
_DEFAULT_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    base_delay_seconds=1.0,
    retryable_exceptions=(httpx.TransportError,),
)

_STATE_MAP: dict[str, DagRunState] = {
    "queued": DagRunState.QUEUED,
    "running": DagRunState.RUNNING,
    "success": DagRunState.SUCCESS,
    "failed": DagRunState.FAILED,
}


class AirflowOrchestrator(OrchestratorPort):
    """:class:`OrchestratorPort` implementation over the Airflow REST API.

    Attributes:
        base_url: Airflow webserver base URL (trailing slash stripped).
        timeout_seconds: Per-request HTTP timeout.
    """

    def __init__(
        self,
        base_url: str,
        auth_token: str,
        *,
        timeout_seconds: float = 10.0,
        verify_tls: bool = True,
        retry_policy: RetryPolicy | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._retry_policy = retry_policy or _DEFAULT_RETRY_POLICY
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=timeout_seconds,
            verify=verify_tls,
            transport=transport,
        )

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        self._client.close()

    def trigger_dag_run(self, dag_id: str, *, conf: dict[str, Any] | None = None) -> DagRunStatus:
        """POST a new DAG run via ``/api/v1/dags/{dag_id}/dagRuns``.

        Args:
            dag_id: Identifier of the DAG to trigger.
            conf: Optional run configuration payload.

        Returns:
            The initial :class:`DagRunStatus`.

        Raises:
            BackendConnectionError: If the Airflow API is unreachable.
            BackendOperationError: If Airflow rejects the request (e.g.
                unknown DAG id, paused DAG, malformed conf).
        """
        run_id = f"mcp_data_tools__{uuid.uuid4().hex}"
        payload: dict[str, Any] = {"dag_run_id": run_id, "conf": conf or {}}

        @with_retry(self._retry_policy)
        def _post() -> httpx.Response:
            return self._client.post(f"/api/v1/dags/{dag_id}/dagRuns", json=payload)

        response = self._request(_post)
        body = response.json()
        return DagRunStatus(
            dag_id=dag_id,
            run_id=body.get("dag_run_id", run_id),
            state=_STATE_MAP.get(body.get("state", ""), DagRunState.UNKNOWN),
            start_date=_parse_dt(body.get("start_date")),
            end_date=_parse_dt(body.get("end_date")),
        )

    def get_dag_run_status(self, dag_id: str, run_id: str) -> DagRunStatus:
        """GET a DAG run via ``/api/v1/dags/{dag_id}/dagRuns/{run_id}``.

        Args:
            dag_id: Identifier of the DAG.
            run_id: Identifier of the specific run.

        Returns:
            The current :class:`DagRunStatus`.

        Raises:
            BackendConnectionError: If the Airflow API is unreachable.
            BackendOperationError: If the run cannot be found.
        """

        @with_retry(self._retry_policy)
        def _get() -> httpx.Response:
            return self._client.get(f"/api/v1/dags/{dag_id}/dagRuns/{run_id}")

        response = self._request(_get)
        body = response.json()
        return DagRunStatus(
            dag_id=dag_id,
            run_id=run_id,
            state=_STATE_MAP.get(body.get("state", ""), DagRunState.UNKNOWN),
            start_date=_parse_dt(body.get("start_date")),
            end_date=_parse_dt(body.get("end_date")),
        )

    def _request(self, call: Callable[[], httpx.Response]) -> httpx.Response:
        try:
            response = call()
        except httpx.TransportError as exc:
            raise BackendConnectionError(f"Cannot reach Airflow at {self.base_url}: {exc}") from exc
        except RetryExhaustedError as exc:
            # `call` is wrapped in @with_retry; once every attempt is
            # exhausted the transport error arrives wrapped in
            # RetryExhaustedError instead of the raw httpx exception.
            raise BackendConnectionError(
                f"Cannot reach Airflow at {self.base_url} after retries: {exc.last_error}"
            ) from exc
        if response.status_code >= 400:
            raise BackendOperationError(
                f"Airflow API returned {response.status_code}: {response.text}",
                details={"status_code": response.status_code},
            )
        return response


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


__all__ = ["AirflowOrchestrator"]
