"""Tests for ToolRegistry."""

from __future__ import annotations

import pytest

from mcp_data_tools.adapters.airflow import InMemoryOrchestrator
from mcp_data_tools.adapters.audit import InMemoryAuditSink
from mcp_data_tools.adapters.bigquery import InMemoryQueryEngine
from mcp_data_tools.adapters.gcs import InMemoryObjectStorage
from mcp_data_tools.core.config import AppConfig
from mcp_data_tools.core.exceptions import ConfigurationError
from mcp_data_tools.tools.registry import ToolRegistry


def test_registry_registers_only_provided_adapters() -> None:
    config = AppConfig.from_mapping({})
    registry = ToolRegistry(config, audit_sink=InMemoryAuditSink())
    assert registry.tools == {}


def test_registry_registers_bigquery_tools_when_query_engine_provided() -> None:
    config = AppConfig.from_mapping({})
    registry = ToolRegistry(
        config, audit_sink=InMemoryAuditSink(), query_engine=InMemoryQueryEngine()
    )
    expected = {"bigquery_query", "bigquery_estimate_cost", "data_quality_check"}
    assert expected <= registry.tools.keys()


def test_registry_registers_all_adapters() -> None:
    config = AppConfig.from_mapping({})
    registry = ToolRegistry(
        config,
        audit_sink=InMemoryAuditSink(),
        query_engine=InMemoryQueryEngine(),
        object_storage=InMemoryObjectStorage(),
        orchestrator=InMemoryOrchestrator(),
    )
    assert len(registry.tools) == 7


def test_registry_respects_enabled_tools_allow_list() -> None:
    config = AppConfig.from_mapping({"server": {"enabled_tools": ["bigquery_estimate_cost"]}})
    registry = ToolRegistry(
        config, audit_sink=InMemoryAuditSink(), query_engine=InMemoryQueryEngine()
    )
    assert set(registry.tools) == {"bigquery_estimate_cost"}


def test_registry_rejects_unknown_enabled_tool_name() -> None:
    config = AppConfig.from_mapping({"server": {"enabled_tools": ["not_a_real_tool"]}})
    with pytest.raises(ConfigurationError):
        ToolRegistry(config, audit_sink=InMemoryAuditSink(), query_engine=InMemoryQueryEngine())


def test_registry_get_raises_for_unknown_tool() -> None:
    config = AppConfig.from_mapping({})
    registry = ToolRegistry(config, audit_sink=InMemoryAuditSink())
    with pytest.raises(ConfigurationError):
        registry.get("nonexistent")
