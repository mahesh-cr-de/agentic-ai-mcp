"""Composition root: builds real adapters and the tool registry from config.

This is the only module in the codebase that is allowed to know about
*both* the concrete adapter classes *and* the configuration schema. Every
other module depends on the port interfaces or on already-constructed
objects, which is what keeps the domain/tool layer trivially testable.
"""

from __future__ import annotations

from mcp_data_tools.adapters.airflow import AirflowOrchestrator
from mcp_data_tools.adapters.audit import LocalJsonlAuditSink, StdoutAuditSink
from mcp_data_tools.adapters.bigquery import BigQueryQueryEngine
from mcp_data_tools.adapters.gcs import GcsObjectStorage
from mcp_data_tools.core.config import AppConfig, AuditSinkKind
from mcp_data_tools.core.exceptions import ConfigurationError
from mcp_data_tools.ports.interfaces import AuditSinkPort
from mcp_data_tools.tools.registry import ToolRegistry


def build_audit_sink(config: AppConfig) -> AuditSinkPort:
    """Construct the configured audit sink.

    Args:
        config: The application configuration.

    Returns:
        A concrete :class:`AuditSinkPort` implementation.

    Raises:
        ConfigurationError: If ``config.audit.kind`` requires a backend
            not yet implemented (e.g. ``bigquery``) or is unrecognized.
    """
    kind = config.audit.kind
    if kind == AuditSinkKind.LOCAL_JSONL:
        return LocalJsonlAuditSink(config.audit.path)
    if kind == AuditSinkKind.STDOUT:
        return StdoutAuditSink()
    if kind == AuditSinkKind.BIGQUERY:
        raise ConfigurationError(
            "audit.kind=bigquery is reserved for a future release; "
            "use local_jsonl or stdout today (see the Roadmap section in README.md)"
        )
    raise ConfigurationError(f"Unrecognized audit.kind: {kind!r}")  # pragma: no cover


def build_tool_registry(config: AppConfig) -> ToolRegistry:
    """Build the full :class:`ToolRegistry` for a validated config.

    Args:
        config: The application configuration. Sections (``bigquery``,
            ``gcs``, ``airflow``) that are ``None`` simply result in the
            corresponding tools not being registered.

    Returns:
        A :class:`ToolRegistry` ready to be wired into the MCP server.
    """
    audit_sink = build_audit_sink(config)

    query_engine = None
    if config.bigquery is not None:
        credentials = config.bigquery.credentials.resolve() if config.bigquery.credentials else None
        query_engine = BigQueryQueryEngine(
            project_id=config.bigquery.project_id,
            location=config.bigquery.location,
            credentials=credentials,
        )

    object_storage = None
    if config.gcs is not None:
        credentials = config.gcs.credentials.resolve() if config.gcs.credentials else None
        object_storage = GcsObjectStorage(project_id=config.gcs.project_id, credentials=credentials)

    orchestrator = None
    if config.airflow is not None:
        orchestrator = AirflowOrchestrator(
            base_url=config.airflow.base_url,
            auth_token=config.airflow.auth_token.resolve(),
            timeout_seconds=config.airflow.timeout_seconds,
            verify_tls=config.airflow.verify_tls,
        )

    return ToolRegistry(
        config,
        audit_sink=audit_sink,
        query_engine=query_engine,
        object_storage=object_storage,
        orchestrator=orchestrator,
    )


__all__ = ["build_audit_sink", "build_tool_registry"]
