"""The ``data_quality_check`` MCP tool."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, ClassVar

from mcp_data_tools.core.config import GuardrailConfig
from mcp_data_tools.guardrails.engine import GuardrailEngine
from mcp_data_tools.ports.interfaces import QueryEnginePort
from mcp_data_tools.tools.base import ToolHandler
from mcp_data_tools.tools.data_quality.strategies import get_strategy


class DataQualityCheckTool(ToolHandler):
    """Runs one or more configurable data-quality checks against a table.

    Each check compiles to a single lightweight aggregate SQL query (one
    row returned), so the same guardrail path (dry-run → allow-list/cost
    check → execute) used by :class:`~mcp_data_tools.tools.bigquery_tools.BigQueryQueryTool`
    applies here as well — a data-quality check can never scan more than
    the cost ceiling permits, and can never touch a non-allow-listed table.
    """

    name = "data_quality_check"
    description = (
        "Run one or more data-quality checks (null_rate, uniqueness, "
        "freshness, row_count) against an allow-listed BigQuery table and "
        "report pass/fail per check."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "table": {
                "type": "string",
                "description": "Fully-qualified project.dataset.table.",
            },
            "checks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["null_rate", "uniqueness", "freshness", "row_count"],
                        },
                        "column": {"type": "string"},
                        "max_null_rate": {"type": "number"},
                        "max_duplicates": {"type": "number"},
                        "max_age_hours": {"type": "number"},
                        "min_rows": {"type": "number"},
                    },
                    "required": ["type"],
                },
                "minItems": 1,
            },
        },
        "required": ["table", "checks"],
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
        """Run every requested check against ``arguments["table"]``.

        Args:
            arguments: Must contain ``table`` and ``checks`` (a list of
                per-check parameter dicts; see ``input_schema``).
            actor: Calling agent/session identifier.

        Returns:
            A dict with ``table``, ``overall_passed``, and ``checks`` (a
            list of per-check result dicts).

        Raises:
            mcp_data_tools.core.exceptions.GuardrailViolationError: If the
                table is not allow-listed or a check's query would exceed
                the cost ceiling.
            mcp_data_tools.core.exceptions.ConfigurationError: If an
                unknown check type is requested.
            mcp_data_tools.core.exceptions.BackendOperationError: If a
                check query fails to execute.
        """
        table = arguments["table"]
        results = []
        for check_spec in arguments["checks"]:
            check_type = check_spec["type"]
            strategy = get_strategy(check_type)
            sql = strategy.build_sql(table, check_spec)

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
                row_limit=1,
            )
            row = result.rows[0] if result.rows else {}
            check_result = strategy.evaluate(row, table, check_spec)
            results.append(asdict(check_result))

        return {
            "table": table,
            "overall_passed": all(r["passed"] for r in results),
            "checks": results,
        }


__all__ = ["DataQualityCheckTool"]
