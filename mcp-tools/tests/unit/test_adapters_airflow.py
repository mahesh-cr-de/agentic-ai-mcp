"""Tests for the Airflow orchestrator adapters (real, via httpx.MockTransport, and mock)."""

from __future__ import annotations

import httpx
import pytest

from mcp_data_tools.adapters.airflow import AirflowOrchestrator, InMemoryOrchestrator
from mcp_data_tools.core.exceptions import BackendConnectionError, BackendOperationError
from mcp_data_tools.core.retry import RetryPolicy
from mcp_data_tools.ports.models import DagRunState


def test_in_memory_orchestrator_trigger_and_status() -> None:
    orch = InMemoryOrchestrator(known_dag_ids={"ingest_orders"})
    status = orch.trigger_dag_run("ingest_orders", conf={"date": "2026-07-07"})
    assert status.state is DagRunState.SUCCESS
    fetched = orch.get_dag_run_status("ingest_orders", status.run_id)
    assert fetched.run_id == status.run_id


def test_in_memory_orchestrator_rejects_unknown_dag() -> None:
    orch = InMemoryOrchestrator(known_dag_ids=set())
    with pytest.raises(BackendOperationError):
        orch.trigger_dag_run("unknown_dag")


def test_in_memory_orchestrator_unknown_run_raises() -> None:
    orch = InMemoryOrchestrator(known_dag_ids={"d"})
    with pytest.raises(BackendOperationError):
        orch.get_dag_run_status("d", "no-such-run")


def _airflow_with_transport(handler) -> AirflowOrchestrator:
    return AirflowOrchestrator(
        "http://airflow.local", "token", transport=httpx.MockTransport(handler)
    )


def test_real_adapter_trigger_dag_run_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/dags/ingest_orders/dagRuns"
        assert request.headers["authorization"] == "Bearer token"
        return httpx.Response(
            200,
            json={"dag_run_id": "run-1", "state": "queued", "start_date": None, "end_date": None},
        )

    orch = _airflow_with_transport(handler)
    status = orch.trigger_dag_run("ingest_orders")
    assert status.dag_id == "ingest_orders"
    assert status.run_id == "run-1"
    assert status.state is DagRunState.QUEUED


def test_real_adapter_get_dag_run_status_parses_dates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "state": "success",
                "start_date": "2026-07-07T00:00:00+00:00",
                "end_date": "2026-07-07T00:05:00+00:00",
            },
        )

    orch = _airflow_with_transport(handler)
    status = orch.get_dag_run_status("ingest_orders", "run-1")
    assert status.state is DagRunState.SUCCESS
    assert status.start_date is not None
    assert status.end_date is not None


def test_real_adapter_raises_backend_operation_error_on_4xx() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="DAG not found")

    orch = _airflow_with_transport(handler)
    with pytest.raises(BackendOperationError):
        orch.trigger_dag_run("missing_dag")


def test_real_adapter_raises_backend_connection_error_on_transport_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    orch = AirflowOrchestrator(
        "http://airflow.local",
        "token",
        transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(
            max_attempts=2, base_delay_seconds=0, retryable_exceptions=(httpx.TransportError,)
        ),
    )
    with pytest.raises(BackendConnectionError):
        orch.trigger_dag_run("ingest_orders")


def test_real_adapter_strips_trailing_slash_from_base_url() -> None:
    orch = AirflowOrchestrator("http://airflow.local/", "token")
    assert orch.base_url == "http://airflow.local"
    orch.close()
