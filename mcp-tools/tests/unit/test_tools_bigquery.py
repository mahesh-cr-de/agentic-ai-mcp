"""Tests for the BigQuery MCP tools."""

from __future__ import annotations

import pytest

from mcp_data_tools.adapters.bigquery import InMemoryQueryEngine
from mcp_data_tools.core.config import GuardrailConfig
from mcp_data_tools.core.exceptions import GuardrailViolationError
from mcp_data_tools.guardrails.engine import GuardrailEngine
from mcp_data_tools.tools.bigquery_tools import BigQueryEstimateCostTool, BigQueryQueryTool


@pytest.fixture
def query_engine() -> InMemoryQueryEngine:
    eng = InMemoryQueryEngine()
    eng.seed_table("proj.sales.orders", [{"id": i, "amount": float(i)} for i in range(20)])
    return eng


def test_estimate_cost_tool_returns_projection(
    guardrail_engine: GuardrailEngine, query_engine: InMemoryQueryEngine
) -> None:
    tool = BigQueryEstimateCostTool(guardrail_engine, query_engine)
    result = tool.execute({"sql": "SELECT * FROM `proj.sales.orders`"}, actor="agent-1")
    assert result["referenced_tables"] == ["proj.sales.orders"]
    assert result["estimated_bytes_processed"] == 20 * 128
    assert query_engine.executed_queries == []  # estimate never executes


def test_estimate_cost_tool_denies_non_allow_listed_table(
    guardrail_engine: GuardrailEngine, query_engine: InMemoryQueryEngine
) -> None:
    query_engine.seed_table("proj.hr.salaries", [{"id": 1}])
    tool = BigQueryEstimateCostTool(guardrail_engine, query_engine)
    with pytest.raises(GuardrailViolationError):
        tool.execute({"sql": "SELECT * FROM `proj.hr.salaries`"}, actor="agent-1")


def test_query_tool_executes_allowed_query(
    guardrail_engine: GuardrailEngine,
    query_engine: InMemoryQueryEngine,
    guardrail_config: GuardrailConfig,
) -> None:
    tool = BigQueryQueryTool(guardrail_engine, query_engine, guardrail_config)
    result = tool.execute(
        {"sql": "SELECT * FROM `proj.sales.orders`", "row_limit": 5}, actor="agent-1"
    )
    assert len(result["rows"]) == 5
    assert result["total_rows_in_result_set"] == 20


def test_query_tool_caps_row_limit_at_config_ceiling(
    guardrail_engine: GuardrailEngine,
    query_engine: InMemoryQueryEngine,
    guardrail_config: GuardrailConfig,
) -> None:
    tool = BigQueryQueryTool(guardrail_engine, query_engine, guardrail_config)
    result = tool.execute(
        {"sql": "SELECT * FROM `proj.sales.orders`", "row_limit": 10_000}, actor="agent-1"
    )
    assert len(result["rows"]) <= guardrail_config.max_rows_returned


def test_query_tool_denies_write_statement_without_touching_backend(
    guardrail_engine: GuardrailEngine,
    query_engine: InMemoryQueryEngine,
    guardrail_config: GuardrailConfig,
) -> None:
    tool = BigQueryQueryTool(guardrail_engine, query_engine, guardrail_config)
    with pytest.raises(GuardrailViolationError):
        tool.execute({"sql": "DELETE FROM `proj.sales.orders`"}, actor="agent-1")
    assert query_engine.executed_queries == []


def test_query_tool_preflight_denies_disallowed_table_before_backend_call(
    guardrail_engine: GuardrailEngine,
    query_engine: InMemoryQueryEngine,
    guardrail_config: GuardrailConfig,
) -> None:
    tool = BigQueryQueryTool(guardrail_engine, query_engine, guardrail_config)
    with pytest.raises(GuardrailViolationError):
        tool.execute({"sql": "SELECT * FROM `proj.hr.salaries`"}, actor="agent-1")
    # The mock engine has no `proj.hr.salaries` table seeded at all — if the
    # preflight check had not short-circuited, estimate_cost would have
    # raised BackendOperationError instead of GuardrailViolationError.
    assert query_engine.executed_queries == []
