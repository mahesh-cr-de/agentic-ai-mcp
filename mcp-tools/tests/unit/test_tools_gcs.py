"""Tests for the GCS MCP tools."""

from __future__ import annotations

import pytest

from mcp_data_tools.adapters.gcs import InMemoryObjectStorage
from mcp_data_tools.core.exceptions import GuardrailViolationError
from mcp_data_tools.guardrails.engine import GuardrailEngine
from mcp_data_tools.tools.gcs_tools import GcsInspectObjectTool, GcsListObjectsTool


@pytest.fixture
def storage() -> InMemoryObjectStorage:
    store = InMemoryObjectStorage()
    store.seed_object("allowed-bucket", "raw/a.csv", size_bytes=100)
    store.seed_object("allowed-bucket", "raw/b.csv", size_bytes=200)
    return store


def test_inspect_object_returns_metadata(
    guardrail_engine: GuardrailEngine, storage: InMemoryObjectStorage
) -> None:
    tool = GcsInspectObjectTool(guardrail_engine, storage)
    result = tool.execute({"bucket": "allowed-bucket", "name": "raw/a.csv"}, actor="a")
    assert result["size_bytes"] == 100


def test_inspect_object_denies_non_allow_listed_bucket(
    guardrail_engine: GuardrailEngine, storage: InMemoryObjectStorage
) -> None:
    storage.seed_object("other-bucket", "x.csv")
    tool = GcsInspectObjectTool(guardrail_engine, storage)
    with pytest.raises(GuardrailViolationError):
        tool.execute({"bucket": "other-bucket", "name": "x.csv"}, actor="a")


def test_list_objects_filters_by_prefix(
    guardrail_engine: GuardrailEngine, storage: InMemoryObjectStorage
) -> None:
    tool = GcsListObjectsTool(guardrail_engine, storage)
    result = tool.execute({"bucket": "allowed-bucket", "prefix": "raw/"}, actor="a")
    assert len(result["objects"]) == 2


def test_list_objects_denies_non_allow_listed_bucket(
    guardrail_engine: GuardrailEngine, storage: InMemoryObjectStorage
) -> None:
    tool = GcsListObjectsTool(guardrail_engine, storage)
    with pytest.raises(GuardrailViolationError):
        tool.execute({"bucket": "not-allow-listed"}, actor="a")
