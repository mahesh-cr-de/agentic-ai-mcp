"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from mcp_data_tools.adapters.audit import InMemoryAuditSink
from mcp_data_tools.core.config import GuardrailConfig
from mcp_data_tools.guardrails.engine import GuardrailEngine


@pytest.fixture
def audit_sink() -> InMemoryAuditSink:
    """A fresh in-memory audit sink for each test."""
    return InMemoryAuditSink()


@pytest.fixture
def guardrail_config() -> GuardrailConfig:
    """A permissive-but-bounded guardrail config for tests to override."""
    return GuardrailConfig(
        allowed_table_patterns=["proj.sales.*"],
        allowed_bucket_patterns=["allowed-bucket"],
        allowed_dag_patterns=["ingest_*"],
        max_bytes_billed=1_000_000,
        max_rows_returned=100,
    )


@pytest.fixture
def guardrail_engine(
    guardrail_config: GuardrailConfig, audit_sink: InMemoryAuditSink
) -> GuardrailEngine:
    """A :class:`GuardrailEngine` wired to the standard test config/audit sink."""
    return GuardrailEngine(guardrail_config, audit_sink)
