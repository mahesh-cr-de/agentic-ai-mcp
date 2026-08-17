"""In-memory :class:`ObjectStoragePort` used by unit tests and examples."""

from __future__ import annotations

from datetime import UTC, datetime

from mcp_data_tools.core.exceptions import BackendOperationError
from mcp_data_tools.ports.interfaces import ObjectStoragePort
from mcp_data_tools.ports.models import ObjectMetadata


class InMemoryObjectStorage(ObjectStoragePort):
    """A fake bucket registry keyed by ``(bucket, name)``.

    Example:
        >>> store = InMemoryObjectStorage()
        >>> store.seed_object("my-bucket", "raw/orders.csv", size_bytes=2048)
        >>> meta = store.get_object_metadata("my-bucket", "raw/orders.csv")
        >>> meta.size_bytes
        2048
    """

    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], ObjectMetadata] = {}

    def seed_object(
        self,
        bucket: str,
        name: str,
        *,
        size_bytes: int = 0,
        content_type: str | None = "application/octet-stream",
        updated_at: datetime | None = None,
    ) -> None:
        """Register a fake object.

        Args:
            bucket: Bucket name.
            name: Object key/path.
            size_bytes: Simulated object size.
            content_type: Simulated MIME type.
            updated_at: Simulated last-modified timestamp; defaults to now.
        """
        self._objects[(bucket, name)] = ObjectMetadata(
            bucket=bucket,
            name=name,
            size_bytes=size_bytes,
            content_type=content_type,
            updated_at=updated_at or datetime.now(UTC),
            etag=f"mock-etag-{len(self._objects)}",
        )

    def get_object_metadata(self, bucket: str, name: str) -> ObjectMetadata:
        """Return previously seeded metadata for one object.

        Args:
            bucket: Bucket name.
            name: Object key/path.

        Returns:
            The seeded :class:`ObjectMetadata`.

        Raises:
            BackendOperationError: If no object was seeded at that path.
        """
        key = (bucket, name)
        if key not in self._objects:
            raise BackendOperationError(f"No such object: gs://{bucket}/{name}")
        return self._objects[key]

    def list_objects(
        self, bucket: str, *, prefix: str = "", max_results: int = 100
    ) -> tuple[ObjectMetadata, ...]:
        """List seeded objects in a bucket matching a prefix.

        Args:
            bucket: Bucket name.
            prefix: Key prefix filter.
            max_results: Maximum number of objects to return.

        Returns:
            A tuple of :class:`ObjectMetadata`.
        """
        matches = [
            meta
            for (obj_bucket, name), meta in self._objects.items()
            if obj_bucket == bucket and name.startswith(prefix)
        ]
        matches.sort(key=lambda meta: meta.name)
        return tuple(matches[:max_results])


__all__ = ["InMemoryObjectStorage"]
