"""MCP tools exposing governed GCS inspection capability.

Note:
    These tools are intentionally read/inspect-only (metadata and
    listing); no tool in this package can write, delete, or download an
    object's contents, which keeps the guardrail surface small and the
    IAM role required by the service account minimal
    (``roles/storage.objectViewer``).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, ClassVar

from mcp_data_tools.guardrails.engine import GuardrailEngine
from mcp_data_tools.ports.interfaces import ObjectStoragePort
from mcp_data_tools.tools.base import ToolHandler


class GcsInspectObjectTool(ToolHandler):
    """Fetches metadata for a single GCS object."""

    name = "gcs_inspect_object"
    description = "Fetch metadata (size, content type, last-modified) for a GCS object."
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "bucket": {"type": "string"},
            "name": {"type": "string", "description": "Object key/path within the bucket."},
        },
        "required": ["bucket", "name"],
        "additionalProperties": False,
    }

    def __init__(self, guardrails: GuardrailEngine, storage: ObjectStoragePort) -> None:
        super().__init__(guardrails)
        self._storage = storage

    def execute(self, arguments: dict[str, Any], *, actor: str) -> dict[str, Any]:
        """Fetch metadata for one object.

        Args:
            arguments: Must contain ``bucket`` and ``name``.
            actor: Calling agent/session identifier.

        Returns:
            A dict describing the object's metadata.

        Raises:
            mcp_data_tools.core.exceptions.GuardrailViolationError: If the
                bucket is not allow-listed.
            mcp_data_tools.core.exceptions.BackendOperationError: If the
                object does not exist.
        """
        bucket, name = arguments["bucket"], arguments["name"]
        decision = self.guardrails.authorize_gcs_access(bucket=bucket, actor=actor)
        self.guardrails.require(decision)

        metadata = self._storage.get_object_metadata(bucket, name)
        return asdict(metadata)


class GcsListObjectsTool(ToolHandler):
    """Lists GCS objects under a prefix."""

    name = "gcs_list_objects"
    description = "List objects in a GCS bucket under an optional key prefix."
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "bucket": {"type": "string"},
            "prefix": {"type": "string", "default": ""},
            "max_results": {"type": "integer", "minimum": 1, "default": 100},
        },
        "required": ["bucket"],
        "additionalProperties": False,
    }

    def __init__(self, guardrails: GuardrailEngine, storage: ObjectStoragePort) -> None:
        super().__init__(guardrails)
        self._storage = storage

    def execute(self, arguments: dict[str, Any], *, actor: str) -> dict[str, Any]:
        """List objects under a prefix.

        Args:
            arguments: Must contain ``bucket``; may contain ``prefix`` and
                ``max_results``.
            actor: Calling agent/session identifier.

        Returns:
            A dict with key ``objects`` (a list of metadata dicts).

        Raises:
            mcp_data_tools.core.exceptions.GuardrailViolationError: If the
                bucket is not allow-listed.
        """
        bucket = arguments["bucket"]
        decision = self.guardrails.authorize_gcs_access(bucket=bucket, actor=actor)
        self.guardrails.require(decision)

        objects = self._storage.list_objects(
            bucket,
            prefix=arguments.get("prefix", ""),
            max_results=int(arguments.get("max_results", 100)),
        )
        return {"objects": [asdict(obj) for obj in objects]}


__all__ = ["GcsInspectObjectTool", "GcsListObjectsTool"]
