"""MCP tools exposing governed BigQuery query capability."""

from __future__ import annotations

from typing import Any, ClassVar

from mcp_data_tools.core.config import GuardrailConfig
from mcp_data_tools.guardrails.engine import GuardrailEngine
from mcp_data_tools.ports.interfaces import QueryEnginePort
from mcp_data_tools.tools.base import ToolHandler


class BigQueryEstimateCostTool(ToolHandler):
    """Dry-runs a SQL query and reports its projected cost without executing it.

    This tool never returns data rows; it is intended for an agent to
    check a query's cost/table footprint before deciding whether to call
    :class:`BigQueryQueryTool`.
    """

    name = "bigquery_estimate_cost"
    description = (
        "Dry-run a SQL query against BigQuery and return the projected "
        "bytes scanned, estimated USD cost, and referenced tables. Does "
        "not execute the query or return any rows."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "The SQL statement to estimate."},
        },
        "required": ["sql"],
        "additionalProperties": False,
    }

    def __init__(self, guardrails: GuardrailEngine, query_engine: QueryEnginePort) -> None:
        super().__init__(guardrails)
        self._query_engine = query_engine

    def execute(self, arguments: dict[str, Any], *, actor: str) -> dict[str, Any]:
        """Estimate the cost of ``arguments["sql"]``.

        Args:
            arguments: Must contain ``sql``.
            actor: Calling agent/session identifier.

        Returns:
            A dict with ``estimated_bytes_processed``,
            ``estimated_cost_usd``, and ``referenced_tables``.

        Raises:
            mcp_data_tools.core.exceptions.GuardrailViolationError: If the
                referenced tables are not allow-listed.
            mcp_data_tools.core.exceptions.BackendOperationError: If the
                dry run fails.
        """
        sql = arguments["sql"]
        preflight = self.guardrails.preflight_check_sql(sql=sql, actor=actor)
        if preflight is not None:
            self.guardrails.require(preflight)

        estimate = self._query_engine.estimate_cost(sql)

        decision = self.guardrails.authorize_query(
            sql=sql,
            referenced_tables=estimate.referenced_tables,
            estimated_bytes=estimate.estimated_bytes_processed,
            actor=actor,
        )
        self.guardrails.require(decision)

        return {
            "estimated_bytes_processed": estimate.estimated_bytes_processed,
            "estimated_cost_usd": estimate.estimated_cost_usd,
            "referenced_tables": list(estimate.referenced_tables),
        }


class BigQueryQueryTool(ToolHandler):
    """Executes a read-only SQL query under enforced cost and row ceilings.

    The flow is always: dry run → guardrail check (allow-list, read-only,
    cost ceiling) → execute with the ceiling passed through to the
    backend so it aborts rather than exceed it, even if the dry-run
    estimate was wrong (e.g. due to a race with concurrent table growth).
    """

    name = "bigquery_query"
    description = (
        "Execute a read-only SQL query against BigQuery. The query must "
        "reference only allow-listed tables and stay within the "
        "configured byte/row ceilings; every call is dry-run estimated "
        "and audit-logged before execution."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "The SQL statement to execute."},
            "row_limit": {
                "type": "integer",
                "description": "Maximum rows to return (capped by server policy).",
                "minimum": 1,
            },
        },
        "required": ["sql"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        guardrails: GuardrailEngine,
        query_engine: QueryEnginePort,
        guardrail_config: GuardrailConfig,
    ) -> None:
        super().__init__(guardrails)
        self._query_engine = query_engine
        self._guardrail_config = guardrail_config

    def execute(self, arguments: dict[str, Any], *, actor: str) -> dict[str, Any]:
        """Run ``arguments["sql"]`` under enforced guardrails.

        Args:
            arguments: Must contain ``sql``; may contain ``row_limit``.
            actor: Calling agent/session identifier.

        Returns:
            A dict with ``rows``, ``total_rows_in_result_set``,
            ``bytes_processed``, and ``job_id``.

        Raises:
            mcp_data_tools.core.exceptions.GuardrailViolationError: If the
                query fails any policy check.
            mcp_data_tools.core.exceptions.BackendOperationError: If
                execution fails.
        """
        sql = arguments["sql"]
        max_rows = self._guardrail_config.max_rows_returned
        requested_row_limit = int(arguments.get("row_limit", max_rows))
        row_limit = min(requested_row_limit, max_rows)

        preflight = self.guardrails.preflight_check_sql(sql=sql, actor=actor)
        if preflight is not None:
            self.guardrails.require(preflight)

        estimate = self._query_engine.estimate_cost(sql)
        decision = self.guardrails.authorize_query(
            sql=sql,
            referenced_tables=estimate.referenced_tables,
            estimated_bytes=estimate.estimated_bytes_processed,
            actor=actor,
        )
        self.guardrails.require(decision)

        result = self._query_engine.execute(
            sql,
            max_bytes_billed=self._guardrail_config.max_bytes_billed,
            row_limit=row_limit,
        )
        return {
            "rows": [dict(row) for row in result.rows],
            "total_rows_in_result_set": result.total_rows_in_result_set,
            "bytes_processed": result.bytes_processed,
            "job_id": result.job_id,
        }


__all__ = ["BigQueryEstimateCostTool", "BigQueryQueryTool"]
