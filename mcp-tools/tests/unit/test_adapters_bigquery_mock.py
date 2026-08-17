"""Tests for InMemoryQueryEngine."""

from __future__ import annotations

import pytest

from mcp_data_tools.adapters.bigquery import InMemoryQueryEngine
from mcp_data_tools.core.exceptions import BackendOperationError


@pytest.fixture
def engine() -> InMemoryQueryEngine:
    eng = InMemoryQueryEngine()
    eng.seed_table("proj.sales.orders", [{"id": i} for i in range(10)])
    return eng


def test_estimate_cost_reports_referenced_tables(engine: InMemoryQueryEngine) -> None:
    estimate = engine.estimate_cost("SELECT * FROM `proj.sales.orders`")
    assert estimate.referenced_tables == ("proj.sales.orders",)
    assert estimate.estimated_bytes_processed == 10 * 128


def test_execute_respects_row_limit(engine: InMemoryQueryEngine) -> None:
    result = engine.execute(
        "SELECT * FROM `proj.sales.orders`",
        max_bytes_billed=10_000,
        row_limit=3,
    )
    assert len(result.rows) == 3
    assert result.total_rows_in_result_set == 10


def test_execute_raises_when_over_billing_ceiling(engine: InMemoryQueryEngine) -> None:
    with pytest.raises(BackendOperationError):
        engine.execute("SELECT * FROM `proj.sales.orders`", max_bytes_billed=1, row_limit=10)


def test_execute_raises_for_unknown_table(engine: InMemoryQueryEngine) -> None:
    with pytest.raises(BackendOperationError):
        engine.execute("SELECT * FROM `proj.unknown.table`", max_bytes_billed=10_000, row_limit=10)


def test_execute_raises_when_no_table_found(engine: InMemoryQueryEngine) -> None:
    with pytest.raises(BackendOperationError):
        engine.execute("SELECT 1", max_bytes_billed=10_000, row_limit=10)


def test_execute_records_query_history(engine: InMemoryQueryEngine) -> None:
    engine.execute("SELECT * FROM `proj.sales.orders`", max_bytes_billed=10_000, row_limit=10)
    assert len(engine.executed_queries) == 1


def test_join_extracts_multiple_tables(engine: InMemoryQueryEngine) -> None:
    engine.seed_table("proj.sales.customers", [{"id": 1}])
    estimate = engine.estimate_cost(
        "SELECT * FROM `proj.sales.orders` o JOIN `proj.sales.customers` c ON o.id = c.id"
    )
    assert set(estimate.referenced_tables) == {"proj.sales.orders", "proj.sales.customers"}
