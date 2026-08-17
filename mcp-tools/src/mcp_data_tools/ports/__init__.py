"""Hexagonal "ports": abstract interfaces the domain/tool layer depends on.

Nothing under ``mcp_data_tools.tools`` or ``mcp_data_tools.guardrails``
imports a concrete cloud SDK directly. Instead it depends on the
interfaces defined here, and a concrete adapter
(``mcp_data_tools.adapters.*``) is injected at server start-up based on
configuration. This is what makes every tool fully unit-testable with an
in-memory mock adapter and zero network access.
"""

from mcp_data_tools.ports.interfaces import (
    AuditSinkPort,
    ObjectStoragePort,
    OrchestratorPort,
    QueryEnginePort,
)
from mcp_data_tools.ports.models import (
    AuditEvent,
    DagRunState,
    DagRunStatus,
    ObjectMetadata,
    QueryCostEstimate,
    QueryResult,
)

__all__ = [
    "AuditEvent",
    "AuditSinkPort",
    "DagRunState",
    "DagRunStatus",
    "ObjectMetadata",
    "ObjectStoragePort",
    "OrchestratorPort",
    "QueryCostEstimate",
    "QueryEnginePort",
    "QueryResult",
]
