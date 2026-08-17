"""Factory that assembles the enabled tool set from configuration.

:class:`ToolRegistry` is the composition root for the tool layer: given an
:class:`~mcp_data_tools.core.config.AppConfig` and the port adapters it
selects (built by :mod:`mcp_data_tools.server.factory`), it constructs the
concrete :class:`~mcp_data_tools.tools.base.ToolHandler` instances and
exposes them as a name-keyed mapping the MCP server wires up.
"""

from __future__ import annotations

from mcp_data_tools.core.config import AppConfig
from mcp_data_tools.core.exceptions import ConfigurationError
from mcp_data_tools.guardrails.engine import GuardrailEngine
from mcp_data_tools.ports.interfaces import (
    AuditSinkPort,
    ObjectStoragePort,
    OrchestratorPort,
    QueryEnginePort,
)
from mcp_data_tools.tools.airflow_tools import AirflowGetDagRunStatusTool, AirflowTriggerDagTool
from mcp_data_tools.tools.base import ToolHandler
from mcp_data_tools.tools.bigquery_tools import BigQueryEstimateCostTool, BigQueryQueryTool
from mcp_data_tools.tools.data_quality.tool import DataQualityCheckTool
from mcp_data_tools.tools.gcs_tools import GcsInspectObjectTool, GcsListObjectsTool


class ToolRegistry:
    """Builds and holds the set of tool handlers active for this server.

    Attributes:
        tools: Mapping of tool name to its :class:`ToolHandler` instance,
            restricted to ``config.server.enabled_tools`` when non-empty.

    Example:
        >>> from mcp_data_tools.core.config import AppConfig
        >>> from mcp_data_tools.adapters.audit import InMemoryAuditSink
        >>> from mcp_data_tools.adapters.bigquery import InMemoryQueryEngine
        >>> config = AppConfig.from_mapping(
        ...     {"guardrails": {"allowed_table_patterns": ["p.d.*"]}}
        ... )
        >>> registry = ToolRegistry(
        ...     config,
        ...     audit_sink=InMemoryAuditSink(),
        ...     query_engine=InMemoryQueryEngine(),
        ... )
        >>> sorted(registry.tools)
        ['bigquery_estimate_cost', 'bigquery_query', 'data_quality_check']
    """

    def __init__(
        self,
        config: AppConfig,
        *,
        audit_sink: AuditSinkPort,
        query_engine: QueryEnginePort | None = None,
        object_storage: ObjectStoragePort | None = None,
        orchestrator: OrchestratorPort | None = None,
    ) -> None:
        self.config = config
        self.guardrails = GuardrailEngine(
            config.guardrails, audit_sink, audit_fail_closed=config.audit.fail_closed
        )
        self.tools: dict[str, ToolHandler] = {}

        if query_engine is not None:
            self._register(BigQueryEstimateCostTool(self.guardrails, query_engine))
            self._register(BigQueryQueryTool(self.guardrails, query_engine, config.guardrails))
            self._register(DataQualityCheckTool(self.guardrails, query_engine, config.guardrails))

        if object_storage is not None:
            self._register(GcsInspectObjectTool(self.guardrails, object_storage))
            self._register(GcsListObjectsTool(self.guardrails, object_storage))

        if orchestrator is not None:
            self._register(AirflowTriggerDagTool(self.guardrails, orchestrator))
            self._register(AirflowGetDagRunStatusTool(self.guardrails, orchestrator))

        enabled = set(config.server.enabled_tools)
        if enabled:
            unknown = enabled - self.tools.keys()
            if unknown:
                raise ConfigurationError(
                    f"server.enabled_tools references unknown tool(s): {sorted(unknown)}"
                )
            self.tools = {name: tool for name, tool in self.tools.items() if name in enabled}

    def _register(self, tool: ToolHandler) -> None:
        self.tools[tool.name] = tool

    def get(self, name: str) -> ToolHandler:
        """Look up a tool handler by name.

        Args:
            name: The tool's registered name.

        Returns:
            The matching :class:`ToolHandler`.

        Raises:
            ConfigurationError: If no tool is registered under ``name``.
        """
        try:
            return self.tools[name]
        except KeyError as exc:
            raise ConfigurationError(f"No such tool registered: {name!r}") from exc


__all__ = ["ToolRegistry"]
