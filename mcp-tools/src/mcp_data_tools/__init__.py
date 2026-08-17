"""mcp-data-tools: A governed Model Context Protocol server for data platform operations.

This package exposes a set of guardrail-enforced tools (BigQuery querying,
GCS inspection, Airflow orchestration, and data-quality checks) to LLM
agents via the Model Context Protocol (MCP). Every tool invocation passes
through a policy engine before touching a real backend, and every decision
is written to an append-only audit trail.

See ``docs/ARCHITECTURE.md`` for the full hexagonal-architecture design.
"""

from importlib import metadata

try:
    __version__ = metadata.version("mcp-data-tools")
except metadata.PackageNotFoundError:  # pragma: no cover - local/dev checkout
    __version__ = "0.0.0+local"

__all__ = ["__version__"]
