"""Policy enforcement layer.

The :class:`~mcp_data_tools.guardrails.engine.GuardrailEngine` is the single
choke point every tool handler must pass through before touching a real
backend. It combines three independent checks — resource allow-listing,
SQL read-only enforcement, and cost/row ceilings — and writes an
:class:`~mcp_data_tools.ports.models.AuditEvent` for every decision,
allowed or denied.
"""

from mcp_data_tools.guardrails.engine import GuardrailDecision, GuardrailEngine

__all__ = ["GuardrailDecision", "GuardrailEngine"]
