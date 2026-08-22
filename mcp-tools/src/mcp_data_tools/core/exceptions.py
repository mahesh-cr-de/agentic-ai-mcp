"""Custom exception hierarchy for mcp-data-tools.

All exceptions raised by this package derive from :class:`McpDataToolsError`
so callers (including the MCP server layer) can catch a single base class
while still being able to branch on specific failure modes when useful.
"""

from __future__ import annotations

from typing import Any


class McpDataToolsError(Exception):
    """Base class for all mcp-data-tools errors.

    Attributes:
        message: Human-readable description of the failure.
        details: Optional structured context (e.g. the offending value)
            that callers can surface in logs or tool-call error payloads
            without parsing the message string.

    Example:
        >>> try:
        ...     raise McpDataToolsError("something failed", details={"x": 1})
        ... except McpDataToolsError as exc:
        ...     print(exc.message, exc.details)
        something failed {'x': 1}
    """

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(McpDataToolsError):
    """Raised when configuration is missing, malformed, or internally inconsistent."""


class GuardrailViolationError(McpDataToolsError):
    """Raised when a requested operation is rejected by the guardrail engine.

    This is the primary error surfaced back to an MCP client when an agent
    attempts an operation that violates policy (e.g. an unbounded query
    against a table that is not on the allow-list).
    """


class BackendConnectionError(McpDataToolsError):
    """Raised when a backend adapter cannot reach the underlying service."""


class BackendOperationError(McpDataToolsError):
    """Raised when a backend adapter's call completes but reports a failure."""


class RetryExhaustedError(McpDataToolsError):
    """Raised when a retried operation fails on every attempt.

    Attributes:
        attempts: Number of attempts made before giving up.
        last_error: The exception raised by the final attempt.
    """

    def __init__(self, message: str, *, attempts: int, last_error: Exception) -> None:
        super().__init__(message, details={"attempts": attempts})
        self.attempts = attempts
        self.last_error = last_error


class AuditWriteError(McpDataToolsError):
    """Raised when an audit event fails to persist to its configured sink.

    Audit failures are treated as operationally significant: by default the
    guardrail engine is configured to fail closed (deny the operation) if
    the audit sink cannot be written to, so this exception is never silently
    swallowed. See ``SECURITY.md`` for the fail-closed rationale.
    """
