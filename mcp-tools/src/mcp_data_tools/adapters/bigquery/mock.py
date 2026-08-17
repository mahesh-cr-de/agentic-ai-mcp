"""In-memory :class:`QueryEnginePort` used by unit tests and examples.

Simulates just enough of BigQuery's behavior — table-reference extraction,
byte-cost accounting, and a billing ceiling — to exercise the guardrail
engine and tool layer end-to-end without any network access or real
credentials.
"""

from __future__ import annotations

from typing import Any

from mcp_data_tools.core.exceptions import BackendOperationError
from mcp_data_tools.core.sql_tables import extract_table_references
from mcp_data_tools.ports.interfaces import QueryEnginePort
from mcp_data_tools.ports.models import QueryCostEstimate, QueryResult

_BYTES_PER_ROW_ESTIMATE = 128


class InMemoryQueryEngine(QueryEnginePort):
    """A fake BigQuery-like engine backed by an in-process table registry.

    Attributes:
        tables: Maps fully-qualified table name to its rows.

    Example:
        >>> engine = InMemoryQueryEngine()
        >>> engine.seed_table(
        ...     "proj.sales.orders", [{"id": 1, "amount": 10.0}]
        ... )
        >>> estimate = engine.estimate_cost(
        ...     "SELECT * FROM `proj.sales.orders`"
        ... )
        >>> estimate.referenced_tables
        ('proj.sales.orders',)
        >>> result = engine.execute(
        ...     "SELECT * FROM `proj.sales.orders`",
        ...     max_bytes_billed=10_000, row_limit=10,
        ... )
        >>> len(result.rows)
        1
    """

    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.executed_queries: list[str] = []

    def seed_table(self, fully_qualified_name: str, rows: list[dict[str, Any]]) -> None:
        """Register fake table data.

        Args:
            fully_qualified_name: ``project.dataset.table`` identifier.
            rows: Rows to serve for any query referencing this table.
        """
        self.tables[fully_qualified_name] = rows

    @staticmethod
    def _extract_tables(sql: str) -> tuple[str, ...]:
        return extract_table_references(sql)

    def _rows_for(self, sql: str) -> list[dict[str, Any]]:
        referenced = self._extract_tables(sql)
        if not referenced:
            raise BackendOperationError("No table reference found in query")
        rows: list[dict[str, Any]] = []
        for table in referenced:
            if table not in self.tables:
                raise BackendOperationError(f"Unknown table in mock engine: {table}")
            rows.extend(self.tables[table])
        return rows

    def estimate_cost(self, sql: str) -> QueryCostEstimate:
        """Estimate cost proportional to the row count of referenced tables.

        Args:
            sql: The SQL statement to estimate.

        Returns:
            A :class:`QueryCostEstimate` computed from seeded table sizes.
        """
        rows = self._rows_for(sql)
        bytes_processed = len(rows) * _BYTES_PER_ROW_ESTIMATE
        return QueryCostEstimate(
            estimated_bytes_processed=bytes_processed,
            estimated_cost_usd=round((bytes_processed / (1024**4)) * 6.25, 8),
            referenced_tables=self._extract_tables(sql),
        )

    def execute(self, sql: str, *, max_bytes_billed: int, row_limit: int) -> QueryResult:
        """Return seeded rows, enforcing the billing ceiling and row cap.

        Args:
            sql: The SQL statement to execute.
            max_bytes_billed: Simulated billing ceiling; exceeding it
                raises :class:`BackendOperationError`.
            row_limit: Maximum number of rows returned.

        Returns:
            A :class:`QueryResult`.

        Raises:
            BackendOperationError: If the simulated byte cost would exceed
                ``max_bytes_billed``, or the query references an unseeded
                table.
        """
        rows = self._rows_for(sql)
        bytes_processed = len(rows) * _BYTES_PER_ROW_ESTIMATE
        if bytes_processed > max_bytes_billed:
            raise BackendOperationError(
                f"Simulated query would bill {bytes_processed} bytes, "
                f"exceeding ceiling of {max_bytes_billed}"
            )
        self.executed_queries.append(sql)
        limited = tuple(rows[:row_limit])
        return QueryResult(
            rows=limited,
            total_rows_in_result_set=len(rows),
            bytes_processed=bytes_processed,
            job_id=f"mock-job-{len(self.executed_queries)}",
        )


__all__ = ["InMemoryQueryEngine"]
