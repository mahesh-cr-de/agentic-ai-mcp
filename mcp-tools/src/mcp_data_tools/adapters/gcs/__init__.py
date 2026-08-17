"""GCS object-storage adapters."""

from mcp_data_tools.adapters.gcs.adapter import GcsObjectStorage
from mcp_data_tools.adapters.gcs.mock import InMemoryObjectStorage

__all__ = ["GcsObjectStorage", "InMemoryObjectStorage"]
