"""Tests for mcp_data_tools.guardrails.engine.GuardrailEngine."""

from __future__ import annotations

import pytest

from mcp_data_tools.adapters.audit import InMemoryAuditSink
from mcp_data_tools.core.config import GuardrailConfig
from mcp_data_tools.core.exceptions import AuditWriteError, GuardrailViolationError
from mcp_data_tools.guardrails.engine import GuardrailEngine
from mcp_data_tools.ports.interfaces import AuditSinkPort
from mcp_data_tools.ports.models import AuditEvent


def test_authorize_query_allows_allow_listed_table(guardrail_engine: GuardrailEngine) -> None:
    decision = guardrail_engine.authorize_query(
        sql="SELECT * FROM `proj.sales.orders`",
        referenced_tables=("proj.sales.orders",),
        estimated_bytes=1000,
        actor="agent-1",
    )
    assert decision.allowed is True


def test_authorize_query_denies_non_allow_listed_table(guardrail_engine: GuardrailEngine) -> None:
    decision = guardrail_engine.authorize_query(
        sql="SELECT * FROM `proj.hr.salaries`",
        referenced_tables=("proj.hr.salaries",),
        estimated_bytes=1000,
        actor="agent-1",
    )
    assert decision.allowed is False
    assert "allow-list" in decision.reason


def test_authorize_query_denies_write_statement(guardrail_engine: GuardrailEngine) -> None:
    decision = guardrail_engine.authorize_query(
        sql="DELETE FROM `proj.sales.orders`",
        referenced_tables=("proj.sales.orders",),
        estimated_bytes=1000,
        actor="agent-1",
    )
    assert decision.allowed is False


def test_authorize_query_denies_over_cost_ceiling(guardrail_engine: GuardrailEngine) -> None:
    decision = guardrail_engine.authorize_query(
        sql="SELECT * FROM `proj.sales.orders`",
        referenced_tables=("proj.sales.orders",),
        estimated_bytes=10_000_000,
        actor="agent-1",
    )
    assert decision.allowed is False
    assert "exceeds ceiling" in decision.reason


def test_authorize_query_denies_when_no_tables_referenced(
    guardrail_engine: GuardrailEngine,
) -> None:
    decision = guardrail_engine.authorize_query(
        sql="SELECT 1",
        referenced_tables=(),
        estimated_bytes=0,
        actor="agent-1",
    )
    assert decision.allowed is False


def test_require_raises_on_denial(guardrail_engine: GuardrailEngine) -> None:
    decision = guardrail_engine.authorize_query(
        sql="SELECT * FROM `proj.hr.salaries`",
        referenced_tables=("proj.hr.salaries",),
        estimated_bytes=1,
        actor="a",
    )
    with pytest.raises(GuardrailViolationError):
        guardrail_engine.require(decision)


def test_require_does_not_raise_on_allow(guardrail_engine: GuardrailEngine) -> None:
    decision = guardrail_engine.authorize_query(
        sql="SELECT * FROM `proj.sales.orders`",
        referenced_tables=("proj.sales.orders",),
        estimated_bytes=1,
        actor="a",
    )
    guardrail_engine.require(decision)  # should not raise


def test_authorize_gcs_access(guardrail_engine: GuardrailEngine) -> None:
    assert guardrail_engine.authorize_gcs_access(bucket="allowed-bucket", actor="a").allowed
    assert not guardrail_engine.authorize_gcs_access(bucket="other-bucket", actor="a").allowed


def test_authorize_dag_trigger(guardrail_engine: GuardrailEngine) -> None:
    assert guardrail_engine.authorize_dag_trigger(dag_id="ingest_orders", actor="a").allowed
    assert not guardrail_engine.authorize_dag_trigger(dag_id="delete_everything", actor="a").allowed


def test_every_decision_is_audited(
    guardrail_engine: GuardrailEngine, audit_sink: InMemoryAuditSink
) -> None:
    guardrail_engine.authorize_gcs_access(bucket="allowed-bucket", actor="agent-x")
    guardrail_engine.authorize_gcs_access(bucket="denied-bucket", actor="agent-x")
    events = audit_sink.read_recent()
    assert len(events) == 2
    decisions = {event.decision for event in events}
    assert decisions == {"allowed", "denied"}
    assert all(event.actor == "agent-x" for event in events)


def test_preflight_check_denies_out_of_policy_table_without_estimate(
    guardrail_engine: GuardrailEngine,
) -> None:
    decision = guardrail_engine.preflight_check_sql(
        sql="SELECT * FROM `proj.hr.salaries`",
        actor="a",
    )
    assert decision is not None
    assert decision.allowed is False


def test_preflight_check_defers_when_table_allow_listed(
    guardrail_engine: GuardrailEngine,
) -> None:
    decision = guardrail_engine.preflight_check_sql(
        sql="SELECT * FROM `proj.sales.orders`",
        actor="a",
    )
    assert decision is None


def test_preflight_check_defers_when_no_table_extractable(
    guardrail_engine: GuardrailEngine,
) -> None:
    decision = guardrail_engine.preflight_check_sql(sql="SELECT 1", actor="a")
    assert decision is None


def test_preflight_check_denies_write_statement(guardrail_engine: GuardrailEngine) -> None:
    decision = guardrail_engine.preflight_check_sql(
        sql="DELETE FROM `proj.sales.orders`",
        actor="a",
    )
    assert decision is not None
    assert decision.allowed is False


class _AlwaysFailingAuditSink(AuditSinkPort):
    def write(self, event: AuditEvent) -> None:
        raise AuditWriteError("simulated audit outage")

    def read_recent(self, limit: int = 100):
        return ()


def test_fail_closed_denies_when_audit_sink_unavailable() -> None:
    engine = GuardrailEngine(
        GuardrailConfig(allowed_bucket_patterns=["*"]),
        _AlwaysFailingAuditSink(),
        audit_fail_closed=True,
    )
    decision = engine.authorize_gcs_access(bucket="any-bucket", actor="a")
    assert decision.allowed is False
    assert "fail-closed" in decision.reason.lower() or "audit" in decision.reason.lower()


def test_fail_open_raises_when_configured(guardrail_config: GuardrailConfig) -> None:
    engine = GuardrailEngine(
        guardrail_config,
        _AlwaysFailingAuditSink(),
        audit_fail_closed=False,
    )
    with pytest.raises(AuditWriteError):
        engine.authorize_gcs_access(bucket="allowed-bucket", actor="a")
