"""Tests for the Airflow MCP tools."""

from __future__ import annotations

import pytest

from mcp_data_tools.adapters.airflow import InMemoryOrchestrator
from mcp_data_tools.core.exceptions import GuardrailViolationError
from mcp_data_tools.guardrails.engine import GuardrailEngine
from mcp_data_tools.tools.airflow_tools import AirflowGetDagRunStatusTool, AirflowTriggerDagTool


@pytest.fixture
def orchestrator() -> InMemoryOrchestrator:
    return InMemoryOrchestrator(known_dag_ids={"ingest_orders"})


def test_trigger_dag_tool_triggers_allow_listed_dag(
    guardrail_engine: GuardrailEngine, orchestrator: InMemoryOrchestrator
) -> None:
    tool = AirflowTriggerDagTool(guardrail_engine, orchestrator)
    result = tool.execute({"dag_id": "ingest_orders"}, actor="a")
    assert result["state"] == "success"


def test_trigger_dag_tool_denies_non_allow_listed_dag(
    guardrail_engine: GuardrailEngine, orchestrator: InMemoryOrchestrator
) -> None:
    tool = AirflowTriggerDagTool(guardrail_engine, orchestrator)
    with pytest.raises(GuardrailViolationError):
        tool.execute({"dag_id": "drop_prod_tables"}, actor="a")


def test_status_tool_returns_status_for_known_run(
    guardrail_engine: GuardrailEngine, orchestrator: InMemoryOrchestrator
) -> None:
    trigger_tool = AirflowTriggerDagTool(guardrail_engine, orchestrator)
    triggered = trigger_tool.execute({"dag_id": "ingest_orders"}, actor="a")

    status_tool = AirflowGetDagRunStatusTool(guardrail_engine, orchestrator)
    status = status_tool.execute(
        {"dag_id": "ingest_orders", "run_id": triggered["run_id"]}, actor="a"
    )
    assert status["run_id"] == triggered["run_id"]


def test_status_tool_denies_non_allow_listed_dag(
    guardrail_engine: GuardrailEngine, orchestrator: InMemoryOrchestrator
) -> None:
    tool = AirflowGetDagRunStatusTool(guardrail_engine, orchestrator)
    with pytest.raises(GuardrailViolationError):
        tool.execute({"dag_id": "not_allow_listed", "run_id": "r1"}, actor="a")
