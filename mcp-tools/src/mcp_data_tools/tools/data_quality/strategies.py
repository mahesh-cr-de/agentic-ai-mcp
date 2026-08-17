"""Data-quality check strategies.

Each strategy knows how to (1) build a single-row aggregate SQL query for
a table/column and (2) evaluate the returned row against a threshold. New
check types are added by implementing :class:`CheckStrategy` and
registering an entry in :data:`CHECK_STRATEGIES` — no changes to the tool
or guardrail layers are required (Open/Closed Principle).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from mcp_data_tools.core.exceptions import ConfigurationError


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Outcome of a single data-quality check.

    Attributes:
        check_type: The strategy's registered name (e.g. ``"null_rate"``).
        table: Fully-qualified table the check ran against.
        column: Column the check inspected, if any.
        passed: Whether the observed metric satisfied the threshold.
        metric_value: The observed value.
        threshold: The configured threshold the metric was compared to.
        detail: Human-readable explanation.
    """

    check_type: str
    table: str
    column: str | None
    passed: bool
    metric_value: float
    threshold: float
    detail: str


class CheckStrategy(ABC):
    """A single kind of data-quality check."""

    name: str

    @abstractmethod
    def build_sql(self, table: str, params: dict[str, Any]) -> str:
        """Build the aggregate SQL statement for this check.

        Args:
            table: Fully-qualified ``project.dataset.table``.
            params: Check-specific parameters (already validated).

        Returns:
            A single-row-result SQL statement.
        """

    @abstractmethod
    def evaluate(self, row: dict[str, Any], table: str, params: dict[str, Any]) -> CheckResult:
        """Evaluate the single result row against the configured threshold.

        Args:
            row: The lone row returned by the query from :meth:`build_sql`.
            table: Fully-qualified table name, echoed into the result.
            params: The same parameters passed to :meth:`build_sql`.

        Returns:
            A :class:`CheckResult`.
        """


class NullRateCheck(CheckStrategy):
    """Fails when the fraction of NULLs in a column exceeds a threshold."""

    name = "null_rate"

    def build_sql(self, table: str, params: dict[str, Any]) -> str:
        column = params["column"]
        return (
            f"SELECT SAFE_DIVIDE(COUNTIF(`{column}` IS NULL), COUNT(*)) AS metric "
            f"FROM `{table}`"
        )

    def evaluate(self, row: dict[str, Any], table: str, params: dict[str, Any]) -> CheckResult:
        threshold = float(params["max_null_rate"])
        value = float(row.get("metric") or 0.0)
        passed = value <= threshold
        return CheckResult(
            check_type=self.name,
            table=table,
            column=params["column"],
            passed=passed,
            metric_value=value,
            threshold=threshold,
            detail=f"null_rate={value:.4f} threshold={threshold:.4f}",
        )


class UniquenessCheck(CheckStrategy):
    """Fails when a column contains any duplicate values."""

    name = "uniqueness"

    def build_sql(self, table: str, params: dict[str, Any]) -> str:
        column = params["column"]
        return f"SELECT COUNT(*) - COUNT(DISTINCT `{column}`) AS metric FROM `{table}`"

    def evaluate(self, row: dict[str, Any], table: str, params: dict[str, Any]) -> CheckResult:
        max_duplicates = float(params.get("max_duplicates", 0))
        value = float(row.get("metric") or 0.0)
        passed = value <= max_duplicates
        return CheckResult(
            check_type=self.name,
            table=table,
            column=params["column"],
            passed=passed,
            metric_value=value,
            threshold=max_duplicates,
            detail=f"duplicate_count={value:.0f} threshold={max_duplicates:.0f}",
        )


class FreshnessCheck(CheckStrategy):
    """Fails when the most recent timestamp in a column is too old."""

    name = "freshness"

    def build_sql(self, table: str, params: dict[str, Any]) -> str:
        column = params["column"]
        return (
            f"SELECT TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(`{column}`), HOUR) "
            f"AS metric FROM `{table}`"
        )

    def evaluate(self, row: dict[str, Any], table: str, params: dict[str, Any]) -> CheckResult:
        threshold = float(params["max_age_hours"])
        value = float(row.get("metric") or float("inf"))
        passed = value <= threshold
        return CheckResult(
            check_type=self.name,
            table=table,
            column=params["column"],
            passed=passed,
            metric_value=value,
            threshold=threshold,
            detail=f"age_hours={value:.2f} threshold={threshold:.2f}",
        )


class RowCountCheck(CheckStrategy):
    """Fails when a table has fewer rows than expected."""

    name = "row_count"

    def build_sql(self, table: str, params: dict[str, Any]) -> str:
        return f"SELECT COUNT(*) AS metric FROM `{table}`"

    def evaluate(self, row: dict[str, Any], table: str, params: dict[str, Any]) -> CheckResult:
        threshold = float(params["min_rows"])
        value = float(row.get("metric") or 0.0)
        passed = value >= threshold
        return CheckResult(
            check_type=self.name,
            table=table,
            column=None,
            passed=passed,
            metric_value=value,
            threshold=threshold,
            detail=f"row_count={value:.0f} min_rows={threshold:.0f}",
        )


CHECK_STRATEGIES: dict[str, CheckStrategy] = {
    "null_rate": NullRateCheck(),
    "uniqueness": UniquenessCheck(),
    "freshness": FreshnessCheck(),
    "row_count": RowCountCheck(),
}


def get_strategy(check_type: str) -> CheckStrategy:
    """Look up a registered check strategy by name.

    Args:
        check_type: One of the keys in :data:`CHECK_STRATEGIES`.

    Returns:
        The matching :class:`CheckStrategy`.

    Raises:
        ConfigurationError: If ``check_type`` is not registered.
    """
    try:
        return CHECK_STRATEGIES[check_type]
    except KeyError as exc:
        raise ConfigurationError(
            f"Unknown check type {check_type!r}; expected one of " f"{sorted(CHECK_STRATEGIES)}"
        ) from exc


__all__ = [
    "CHECK_STRATEGIES",
    "CheckResult",
    "CheckStrategy",
    "FreshnessCheck",
    "NullRateCheck",
    "RowCountCheck",
    "UniquenessCheck",
    "get_strategy",
]
