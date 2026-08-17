"""A query-engine test double whose responses are scripted per call.

Unlike :class:`~mcp_data_tools.adapters.bigquery.mock.InMemoryQueryEngine`
(which echoes raw seeded rows verbatim and is meant to exercise
guardrail/allow-list/cost-ceiling behavior — it does **not** evaluate SQL
aggregate functions), :class:`ScriptedQueryEngine` is for tests that need
to control *exactly* what a query "returns" — e.g. asserting that
``DataQualityCheckTool`` correctly interprets a pre-computed aggregate
result — without depending on any SQL-evaluation capability. This module
is part of the public API specifically so downstream users adding their
own :class:`~mcp_data_tools.tools.data_quality.strategies.CheckStrategy`
or tool have an official way to unit test it.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from mcp_data_tools.ports.interfaces import QueryEnginePort
from mcp_data_tools.ports.models import QueryCostEstimate, QueryResult


class ScriptedQueryEngine(QueryEnginePort):
    """Returns pre-programmed responses regardless of the SQL text.

    Attributes:
        estimates: Queue of :class:`QueryCostEstimate` to return, in
            order, one per :meth:`estimate_cost` call.
        results: Queue of :class:`QueryResult` to return, in order, one
            per :meth:`execute` call.
    """

    def __init__(
        self,
        estimates: list[QueryCostEstimate] | None = None,
        results: list[QueryResult] | None = None,
    ) -> None:
        self.estimates: deque[QueryCostEstimate] = deque(estimates or [])
        self.results: deque[QueryResult] = deque(results or [])
        self.estimate_calls: list[str] = []
        self.execute_calls: list[str] = []

    def estimate_cost(self, sql: str) -> QueryCostEstimate:
        self.estimate_calls.append(sql)
        if not self.estimates:
            raise AssertionError("ScriptedQueryEngine.estimate_cost called with no script left")
        return self.estimates.popleft()

    def execute(self, sql: str, *, max_bytes_billed: int, row_limit: int) -> QueryResult:
        self.execute_calls.append(sql)
        if not self.results:
            raise AssertionError("ScriptedQueryEngine.execute called with no script left")
        return self.results.popleft()


def single_row_result(
    row: dict[str, Any], *, table: str, bytes_processed: int = 100
) -> tuple[QueryCostEstimate, QueryResult]:
    """Build a matching (estimate, result) pair for a single-row aggregate query.

    Args:
        row: The row the "query" should appear to return.
        table: The table name to report as referenced.
        bytes_processed: Simulated bytes processed.

    Returns:
        A tuple ready to feed into :class:`ScriptedQueryEngine`.
    """
    estimate = QueryCostEstimate(
        estimated_bytes_processed=bytes_processed,
        estimated_cost_usd=0.0,
        referenced_tables=(table,),
    )
    result = QueryResult(
        rows=(row,),
        total_rows_in_result_set=1,
        bytes_processed=bytes_processed,
        job_id="scripted-job",
    )
    return estimate, result


__all__ = ["ScriptedQueryEngine", "single_row_result"]
