"""Base abstractions for MCP tool handlers (Command pattern)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from mcp_data_tools.guardrails.engine import GuardrailEngine


class ToolHandler(ABC):
    """A single governed MCP tool.

    Concrete subclasses declare their MCP-facing metadata (``name``,
    ``description``, ``input_schema``) as class attributes and implement
    :meth:`execute` to perform the actual (guardrail-checked) work.

    Attributes:
        guardrails: The shared :class:`GuardrailEngine` every tool must
            consult before calling an adapter.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    input_schema: ClassVar[dict[str, Any]]

    def __init__(self, guardrails: GuardrailEngine) -> None:
        self.guardrails = guardrails

    @abstractmethod
    def execute(self, arguments: dict[str, Any], *, actor: str) -> dict[str, Any]:
        """Run the tool.

        Args:
            arguments: Tool arguments, already validated against
                ``input_schema`` by the MCP server layer.
            actor: Best-effort identifier of the calling agent/session,
                forwarded to the audit trail.

        Returns:
            A JSON-serializable result payload.

        Raises:
            mcp_data_tools.core.exceptions.GuardrailViolationError: If the
                guardrail engine denies the operation.
            mcp_data_tools.core.exceptions.BackendOperationError: If the
                underlying adapter call fails.
        """


__all__ = ["ToolHandler"]
