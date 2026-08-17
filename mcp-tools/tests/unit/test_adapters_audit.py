"""Tests for the audit sink adapters."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mcp_data_tools.adapters.audit import InMemoryAuditSink, LocalJsonlAuditSink, StdoutAuditSink
from mcp_data_tools.ports.models import AuditEvent


def _event(event_id: str = "e1") -> AuditEvent:
    return AuditEvent(
        event_id=event_id,
        timestamp=datetime.now(UTC),
        tool_name="bigquery_query",
        actor="agent-1",
        parameters={"sql": "SELECT 1"},
        decision="allowed",
        reason="ok",
    )


def test_in_memory_sink_stores_and_returns_newest_first() -> None:
    sink = InMemoryAuditSink()
    sink.write(_event("e1"))
    sink.write(_event("e2"))
    events = sink.read_recent()
    assert [e.event_id for e in events] == ["e2", "e1"]


def test_in_memory_sink_respects_max_events() -> None:
    sink = InMemoryAuditSink(max_events=2)
    for i in range(5):
        sink.write(_event(f"e{i}"))
    events = sink.read_recent()
    assert len(events) == 2
    assert [e.event_id for e in events] == ["e4", "e3"]


def test_in_memory_sink_respects_limit() -> None:
    sink = InMemoryAuditSink()
    for i in range(5):
        sink.write(_event(f"e{i}"))
    assert len(sink.read_recent(limit=2)) == 2


def test_local_jsonl_sink_round_trips(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    sink = LocalJsonlAuditSink(path)
    sink.write(_event("e1"))
    sink.write(_event("e2"))

    events = sink.read_recent()
    assert [e.event_id for e in events] == ["e2", "e1"]
    assert events[0].tool_name == "bigquery_query"
    assert events[0].parameters == {"sql": "SELECT 1"}


def test_local_jsonl_sink_returns_empty_when_file_missing(tmp_path) -> None:
    sink = LocalJsonlAuditSink(tmp_path / "missing.jsonl")
    assert sink.read_recent() == ()


def test_local_jsonl_sink_creates_parent_directories(tmp_path) -> None:
    nested = tmp_path / "a" / "b" / "audit.jsonl"
    sink = LocalJsonlAuditSink(nested)
    sink.write(_event())
    assert nested.exists()


def test_stdout_sink_writes_without_error(capsys: pytest.CaptureFixture[str]) -> None:
    sink = StdoutAuditSink()
    sink.write(_event())  # should not raise
    assert sink.read_recent() == ()
