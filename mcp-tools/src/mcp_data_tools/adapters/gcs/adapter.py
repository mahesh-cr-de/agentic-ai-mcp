"""Real GCS adapter, backed by ``google-cloud-storage``.

Imports the SDK lazily; see the note in
``mcp_data_tools.adapters.bigquery.adapter`` for the rationale.
"""

from __future__ import annotations

from typing import Any

from mcp_data_tools.core.exceptions import BackendOperationError
from mcp_data_tools.core.logging import get_logger
from mcp_data_tools.core.retry import RetryPolicy, with_retry
from mcp_data_tools.ports.interfaces import ObjectStoragePort
from mcp_data_tools.ports.models import ObjectMetadata

_LOGGER = get_logger(__name__)
_DEFAULT_RETRY_POLICY = RetryPolicy(max_attempts=3, base_delay_seconds=0.5)


class GcsObjectStorage(ObjectStoragePort):
    """:class:`ObjectStoragePort` implementation backed by Google Cloud Storage."""

    def __init__(
        self,
        project_id: str,
        *,
        credentials: Any | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        try:
            from google.cloud import storage  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - exercised without extra installed
            raise BackendOperationError(
                "google-cloud-storage is required for GcsObjectStorage; "
                "install the 'gcp' extra (pip install mcp-data-tools[gcp])"
            ) from exc

        self.project_id = project_id
        self._retry_policy = retry_policy or _DEFAULT_RETRY_POLICY
        self._client = storage.Client(project=project_id, credentials=credentials)

    def get_object_metadata(self, bucket: str, name: str) -> ObjectMetadata:
        """Fetch metadata for a single blob.

        Args:
            bucket: Bucket name.
            name: Object key/path.

        Returns:
            An :class:`ObjectMetadata`.

        Raises:
            BackendOperationError: If the blob does not exist or the
                backend call fails.
        """

        @with_retry(self._retry_policy)
        def _fetch() -> Any:
            blob = self._client.bucket(bucket).blob(name)
            blob.reload()
            return blob

        try:
            blob = _fetch()
        except Exception as exc:
            raise BackendOperationError(f"Failed to fetch GCS metadata: {exc}") from exc

        return ObjectMetadata(
            bucket=bucket,
            name=name,
            size_bytes=int(blob.size or 0),
            content_type=blob.content_type,
            updated_at=blob.updated,
            etag=blob.etag,
        )

    def list_objects(
        self, bucket: str, *, prefix: str = "", max_results: int = 100
    ) -> tuple[ObjectMetadata, ...]:
        """List blobs under a prefix.

        Args:
            bucket: Bucket name.
            prefix: Key prefix filter.
            max_results: Maximum number of blobs to return.

        Returns:
            A tuple of :class:`ObjectMetadata`.

        Raises:
            BackendOperationError: If the backend call fails.
        """

        @with_retry(self._retry_policy)
        def _list() -> Any:
            return list(self._client.list_blobs(bucket, prefix=prefix, max_results=max_results))

        try:
            blobs = _list()
        except Exception as exc:
            raise BackendOperationError(f"Failed to list GCS objects: {exc}") from exc

        return tuple(
            ObjectMetadata(
                bucket=bucket,
                name=blob.name,
                size_bytes=int(blob.size or 0),
                content_type=blob.content_type,
                updated_at=blob.updated,
                etag=blob.etag,
            )
            for blob in blobs
        )


__all__ = ["GcsObjectStorage"]
