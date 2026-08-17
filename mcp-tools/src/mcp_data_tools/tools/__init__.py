"""MCP tool implementations.

Every tool in this package follows the same shape: a small ``Command``
object (:class:`~mcp_data_tools.tools.base.ToolHandler`) whose
``execute`` method (1) resolves any information it needs (e.g. a BigQuery
dry-run cost estimate), (2) asks the
:class:`~mcp_data_tools.guardrails.engine.GuardrailEngine` for permission,
and (3) only then calls the injected port adapter. No tool ever talks to
an adapter without first passing through the guardrail engine.
"""

from mcp_data_tools.tools.registry import ToolRegistry

__all__ = ["ToolRegistry"]
