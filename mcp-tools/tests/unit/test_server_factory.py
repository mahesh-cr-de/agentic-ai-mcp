"""Tests for mcp_data_tools.server.factory."""

from __future__ import annotations

import pytest

from mcp_data_tools.adapters.audit import LocalJsonlAuditSink, StdoutAuditSink
from mcp_data_tools.core.config import AppConfig
from mcp_data_tools.core.exceptions import ConfigurationError
from mcp_data_tools.server.factory import build_audit_sink, build_tool_registry


def test_build_audit_sink_local_jsonl(tmp_path) -> None:
    audit_path = str(tmp_path / "a.jsonl")
    config = AppConfig.from_mapping({"audit": {"kind": "local_jsonl", "path": audit_path}})
    sink = build_audit_sink(config)
    assert isinstance(sink, LocalJsonlAuditSink)


def test_build_audit_sink_stdout() -> None:
    config = AppConfig.from_mapping({"audit": {"kind": "stdout"}})
    assert isinstance(build_audit_sink(config), StdoutAuditSink)


def test_build_audit_sink_bigquery_not_yet_supported() -> None:
    config = AppConfig.from_mapping({"audit": {"kind": "bigquery", "table": "p.d.t"}})
    with pytest.raises(ConfigurationError):
        build_audit_sink(config)


def test_build_tool_registry_with_no_backends_configured(tmp_path) -> None:
    audit_path = str(tmp_path / "a.jsonl")
    config = AppConfig.from_mapping({"audit": {"kind": "local_jsonl", "path": audit_path}})
    registry = build_tool_registry(config)
    assert registry.tools == {}
