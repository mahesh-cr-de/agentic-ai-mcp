"""Tests for InMemoryObjectStorage."""

from __future__ import annotations

import pytest

from mcp_data_tools.adapters.gcs import InMemoryObjectStorage
from mcp_data_tools.core.exceptions import BackendOperationError


def test_get_object_metadata_round_trip() -> None:
    store = InMemoryObjectStorage()
    store.seed_object("bucket", "path/to/file.csv", size_bytes=2048, content_type="text/csv")
    meta = store.get_object_metadata("bucket", "path/to/file.csv")
    assert meta.size_bytes == 2048
    assert meta.content_type == "text/csv"


def test_get_object_metadata_missing_raises() -> None:
    store = InMemoryObjectStorage()
    with pytest.raises(BackendOperationError):
        store.get_object_metadata("bucket", "missing.csv")


def test_list_objects_filters_by_prefix() -> None:
    store = InMemoryObjectStorage()
    store.seed_object("bucket", "raw/a.csv")
    store.seed_object("bucket", "raw/b.csv")
    store.seed_object("bucket", "curated/c.csv")

    raw_objects = store.list_objects("bucket", prefix="raw/")
    assert {o.name for o in raw_objects} == {"raw/a.csv", "raw/b.csv"}


def test_list_objects_respects_max_results() -> None:
    store = InMemoryObjectStorage()
    for i in range(5):
        store.seed_object("bucket", f"file-{i}.csv")
    assert len(store.list_objects("bucket", max_results=2)) == 2


def test_list_objects_across_buckets_is_isolated() -> None:
    store = InMemoryObjectStorage()
    store.seed_object("bucket-a", "x.csv")
    store.seed_object("bucket-b", "y.csv")
    assert len(store.list_objects("bucket-a")) == 1
