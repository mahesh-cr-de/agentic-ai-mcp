"""The guardrail engine: the single choke point for policy decisions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from mcp_data_tools.core.config import GuardrailConfig
from mcp_data_tools.core.exceptions import AuditWriteError, GuardrailViolationError
from mcp_data_tools.core.logging import get_logger
from mcp_data_tools.core.sql_tables import extract_table_references
from mcp_data_tools.guardrails.patterns import matches_any
from mcp_data_tools.guardrails.sql_policy import is_read_only
from mcp_data_tools.ports.interfaces import AuditSinkPort
from mcp_data_tools.ports.models import AuditEvent

_LOGGER = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GuardrailDecision:
    """Outcome of a guardrail evaluation.

    Attributes:
        allowed: Whether the operation may proceed.
        reason: Human-readable explanation.
        event: The :class:`AuditEvent` that was (or would be) recorded.
    """

    allowed: bool
    reason: str
    event: AuditEvent


class GuardrailEngine:
    """Evaluates and audits every governed operation.

    Attributes:
        config: The active :class:`~mcp_data_tools.core.config.GuardrailConfig`.
        audit_sink: Where every decision (allowed or denied) is recorded.

    Example:
        >>> from mcp_data_tools.adapters.audit import InMemoryAuditSink
        >>> engine = GuardrailEngine(
        ...     GuardrailConfig(allowed_table_patterns=["proj.sales.*"]),
        ...     InMemoryAuditSink(),
        ... )
        >>> decision = engine.authorize_query(
        ...     sql="SELECT * FROM `proj.sales.orders`",
        ...     referenced_tables=("proj.sales.orders",),
        ...     estimated_bytes=1000,
        ...     actor="agent-1",
        ... )
        >>> decision.allowed
        True
    """

    def __init__(
        self,
        config: GuardrailConfig,
        audit_sink: AuditSinkPort,
        *,
        audit_fail_closed: bool = True,
    ) -> None:
        self.config = config
        self.audit_sink = audit_sink
        self.audit_fail_closed = audit_fail_closed

    def authorize_query(
        self,
        *,
        sql: str,
        referenced_tables: tuple[str, ...],
        estimated_bytes: int,
        actor: str,
    ) -> GuardrailDecision:
        """Authorize a BigQuery (or similar) SQL query.

        Args:
            sql: The raw SQL text.
            referenced_tables: Tables the query would read, typically
                obtained from a prior dry-run cost estimate.
            estimated_bytes: Bytes the query is projected to scan.
            actor: Identifier of the calling agent/session, for the audit
                trail.

        Returns:
            A :class:`GuardrailDecision`. Raises rather than returning a
            denied decision when the caller should not proceed; see
            :meth:`require`.

        Raises:
            GuardrailViolationError: If the query is denied and audit
                logging is only advisory (never — denials always return a
                decision; see :meth:`require` for the raising variant).
        """
        parameters: dict[str, Any] = {
            "sql": sql,
            "referenced_tables": list(referenced_tables),
            "estimated_bytes": estimated_bytes,
        }

        if self.config.read_only:
            read_only, sql_reason = is_read_only(sql)
            if not read_only:
                return self._deny("bigquery_query", actor, parameters, sql_reason)

        if not referenced_tables:
            return self._deny(
                "bigquery_query",
                actor,
                parameters,
                "Query does not reference any resolvable table",
            )

        for table in referenced_tables:
            if not matches_any(table, self.config.allowed_table_patterns):
                return self._deny(
                    "bigquery_query",
                    actor,
                    parameters,
                    f"Table {table!r} is not in the allow-list",
                )

        if estimated_bytes > self.config.max_bytes_billed:
            return self._deny(
                "bigquery_query",
                actor,
                parameters,
                f"Estimated {estimated_bytes} bytes exceeds ceiling of "
                f"{self.config.max_bytes_billed}",
            )

        return self._allow("bigquery_query", actor, parameters, "Query passed all guardrails")

    def preflight_check_sql(self, *, sql: str, actor: str) -> GuardrailDecision | None:
        """Cheaply reject obviously out-of-policy SQL before any backend call.

        Tool handlers should call this *before* invoking
        :meth:`~mcp_data_tools.ports.interfaces.QueryEnginePort.estimate_cost`.
        Regex-based table extraction (see
        :mod:`mcp_data_tools.core.sql_tables`) is heuristic, so this method
        only ever returns a *denial* or ``None`` — it never authoritatively
        allows a query. The authoritative allow decision still comes from
        :meth:`authorize_query`, called after the backend's own dry run
        reports the tables it actually resolved.

        Args:
            sql: The raw SQL text.
            actor: Identifier of the calling agent/session.

        Returns:
            A denying :class:`GuardrailDecision` if the query is clearly
            out of policy, or ``None`` if the caller should proceed to the
            authoritative post-dry-run check.
        """
        parameters: dict[str, Any] = {"sql": sql}

        if self.config.read_only:
            read_only, reason = is_read_only(sql)
            if not read_only:
                return self._deny("bigquery_query", actor, parameters, reason)

        candidate_tables = extract_table_references(sql)
        if not candidate_tables:
            # Heuristic extraction found nothing confident; defer to the
            # authoritative check rather than risk a false denial.
            return None

        disallowed = [
            table
            for table in candidate_tables
            if not matches_any(table, self.config.allowed_table_patterns)
        ]
        if disallowed:
            parameters["candidate_tables"] = list(candidate_tables)
            return self._deny(
                "bigquery_query",
                actor,
                parameters,
                f"Table(s) {disallowed} are not in the allow-list (preflight check)",
            )
        return None

    def authorize_gcs_access(self, *, bucket: str, actor: str) -> GuardrailDecision:
        """Authorize read access to a GCS bucket.

        Args:
            bucket: Bucket name the caller wants to read from.
            actor: Identifier of the calling agent/session.

        Returns:
            A :class:`GuardrailDecision`.
        """
        parameters = {"bucket": bucket}
        if not matches_any(bucket, self.config.allowed_bucket_patterns):
            return self._deny(
                "gcs_access",
                actor,
                parameters,
                f"Bucket {bucket!r} is not in the allow-list",
            )
        return self._allow("gcs_access", actor, parameters, "Bucket is allow-listed")

    def authorize_dag_trigger(self, *, dag_id: str, actor: str) -> GuardrailDecision:
        """Authorize triggering an Airflow DAG run.

        Args:
            dag_id: Identifier of the DAG the caller wants to trigger.
            actor: Identifier of the calling agent/session.

        Returns:
            A :class:`GuardrailDecision`.
        """
        parameters = {"dag_id": dag_id}
        if not matches_any(dag_id, self.config.allowed_dag_patterns):
            return self._deny(
                "airflow_trigger_dag",
                actor,
                parameters,
                f"DAG {dag_id!r} is not in the allow-list",
            )
        return self._allow("airflow_trigger_dag", actor, parameters, "DAG is allow-listed")

    @staticmethod
    def require(decision: GuardrailDecision) -> None:
        """Raise if a decision was a denial.

        Args:
            decision: The decision to check.

        Raises:
            GuardrailViolationError: If ``decision.allowed`` is ``False``.
        """
        if not decision.allowed:
            raise GuardrailViolationError(
                decision.reason, details={"event_id": decision.event.event_id}
            )

    def _allow(
        self, tool_name: str, actor: str, parameters: dict[str, Any], reason: str
    ) -> GuardrailDecision:
        return self._record(tool_name, actor, parameters, decision="allowed", reason=reason)

    def _deny(
        self, tool_name: str, actor: str, parameters: dict[str, Any], reason: str
    ) -> GuardrailDecision:
        return self._record(tool_name, actor, parameters, decision="denied", reason=reason)

    def _record(
        self,
        tool_name: str,
        actor: str,
        parameters: dict[str, Any],
        *,
        decision: str,
        reason: str,
    ) -> GuardrailDecision:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            tool_name=tool_name,
            actor=actor,
            parameters=parameters,
            decision=decision,
            reason=reason,
        )
        try:
            self.audit_sink.write(event)
        except AuditWriteError:
            _LOGGER.error(
                "audit write failed",
                extra={"tool_name": tool_name, "actor": actor, "event_id": event.event_id},
            )
            if self.audit_fail_closed:
                # Fail closed: an unauditable action must not be treated as allowed.
                return GuardrailDecision(
                    allowed=False,
                    reason="Denied: audit sink unavailable (fail-closed policy)",
                    event=event,
                )
            raise
        _LOGGER.info(
            "guardrail decision",
            extra={
                "tool_name": tool_name,
                "actor": actor,
                "decision": decision,
                "reason": reason,
                "event_id": event.event_id,
            },
        )
        return GuardrailDecision(allowed=(decision == "allowed"), reason=reason, event=event)


__all__ = ["GuardrailDecision", "GuardrailEngine"]
