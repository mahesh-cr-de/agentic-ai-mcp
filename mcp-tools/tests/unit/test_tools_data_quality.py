"""Tests for DataQualityCheckTool and the check strategies."""

from __future__ import annotations

import pytest

from mcp_data_tools.core.config import GuardrailConfig
from mcp_data_tools.core.exceptions import ConfigurationError, GuardrailViolationError
from mcp_data_tools.guardrails.engine import GuardrailEngine
from mcp_data_tools.testing import ScriptedQueryEngine, single_row_result
from mcp_data_tools.tools.data_quality.strategies import (
    FreshnessCheck,
    NullRateCheck,
    RowCountCheck,
    UniquenessCheck,
    get_strategy,
)
from mcp_data_tools.tools.data_quality.tool import DataQualityCheckTool

TABLE = "proj.sales.orders"


# --- Strategy unit tests: pure logic, no query engine involved -------------


def test_null_rate_check_sql_references_column() -> None:
    sql = NullRateCheck().build_sql(TABLE, {"column": "amount"})
    assert "amount" in sql
    assert TABLE in sql


def test_null_rate_check_passes_under_threshold() -> None:
    params = {"column": "amount", "max_null_rate": 0.1}
    result = NullRateCheck().evaluate({"metric": 0.05}, TABLE, params)
    assert result.passed is True


def test_null_rate_check_fails_over_threshold() -> None:
    params = {"column": "amount", "max_null_rate": 0.1}
    result = NullRateCheck().evaluate({"metric": 0.5}, TABLE, params)
    assert result.passed is False


def test_uniqueness_check_fails_on_duplicates() -> None:
    result = UniquenessCheck().evaluate({"metric": 3}, TABLE, {"column": "id"})
    assert result.passed is False


def test_uniqueness_check_passes_with_zero_duplicates() -> None:
    result = UniquenessCheck().evaluate({"metric": 0}, TABLE, {"column": "id"})
    assert result.passed is True


def test_freshness_check_fails_when_stale() -> None:
    result = FreshnessCheck().evaluate(
        {"metric": 48}, TABLE, {"column": "updated_at", "max_age_hours": 24}
    )
    assert result.passed is False


def test_freshness_check_passes_when_fresh() -> None:
    result = FreshnessCheck().evaluate(
        {"metric": 2}, TABLE, {"column": "updated_at", "max_age_hours": 24}
    )
    assert result.passed is True


def test_row_count_check_fails_below_minimum() -> None:
    result = RowCountCheck().evaluate({"metric": 0}, TABLE, {"min_rows": 1})
    assert result.passed is False


def test_get_strategy_unknown_type_raises() -> None:
    with pytest.raises(ConfigurationError):
        get_strategy("not_a_real_check")


# --- Tool-orchestration tests: guardrails + multi-check aggregation --------


def test_tool_runs_single_check_and_reports_pass(
    guardrail_engine: GuardrailEngine, guardrail_config: GuardrailConfig
) -> None:
    estimate, result = single_row_result({"metric": 0.02}, table=TABLE)
    engine = ScriptedQueryEngine(estimates=[estimate], results=[result])
    tool = DataQualityCheckTool(guardrail_engine, engine, guardrail_config)

    check = {"type": "null_rate", "column": "amount", "max_null_rate": 0.1}
    report = tool.execute({"table": TABLE, "checks": [check]}, actor="agent-1")
    assert report["overall_passed"] is True
    assert report["checks"][0]["passed"] is True


def test_tool_aggregates_multiple_checks_and_fails_if_any_fails(
    guardrail_engine: GuardrailEngine, guardrail_config: GuardrailConfig
) -> None:
    est1, res1 = single_row_result({"metric": 0.02}, table=TABLE)
    est2, res2 = single_row_result({"metric": 500}, table=TABLE)  # row_count too low
    engine = ScriptedQueryEngine(estimates=[est1, est2], results=[res1, res2])
    tool = DataQualityCheckTool(guardrail_engine, engine, guardrail_config)

    report = tool.execute(
        {
            "table": TABLE,
            "checks": [
                {"type": "null_rate", "column": "amount", "max_null_rate": 0.1},
                {"type": "row_count", "min_rows": 1_000_000},
            ],
        },
        actor="agent-1",
    )
    assert report["overall_passed"] is False
    assert report["checks"][0]["passed"] is True
    assert report["checks"][1]["passed"] is False


def test_tool_denies_check_against_non_allow_listed_table(
    guardrail_engine: GuardrailEngine, guardrail_config: GuardrailConfig
) -> None:
    engine = ScriptedQueryEngine()  # never consulted: preflight denies first
    tool = DataQualityCheckTool(guardrail_engine, engine, guardrail_config)

    with pytest.raises(GuardrailViolationError):
        tool.execute(
            {"table": "proj.hr.salaries", "checks": [{"type": "row_count", "min_rows": 1}]},
            actor="agent-1",
        )
    assert engine.estimate_calls == []
