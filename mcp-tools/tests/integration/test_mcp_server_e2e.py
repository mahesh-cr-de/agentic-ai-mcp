"""End-to-end test: a real MCP client talking to our server over in-memory streams.

Uses the MCP SDK's own test harness
(``mcp.shared.memory.create_connected_server_and_client_session``) rather
than hand-rolled fakes, so this test exercises the exact JSON-RPC
request/response path a real MCP client (an LLM agent host) would use:
``list_tools`` and ``call_tool`` over the wire, including JSON
serialization of tool results.
"""

from __future__ import annotations

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_data_tools.adapters.audit import InMemoryAuditSink
from mcp_data_tools.adapters.bigquery import InMemoryQueryEngine
from mcp_data_tools.core.config import AppConfig
from mcp_data_tools.server.mcp_server import build_mcp_server
from mcp_data_tools.tools.registry import ToolRegistry


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _build_registry() -> ToolRegistry:
    config = AppConfig.from_mapping(
        {
            "guardrails": {
                "allowed_table_patterns": ["proj.sales.*"],
                "max_bytes_billed": 1_000_000,
            }
        }
    )
    engine = InMemoryQueryEngine()
    engine.seed_table("proj.sales.orders", [{"id": 1, "amount": 9.99}])
    return ToolRegistry(config, audit_sink=InMemoryAuditSink(), query_engine=engine), config


@pytest.mark.anyio
async def test_list_tools_over_mcp_protocol() -> None:
    registry, config = _build_registry()
    server = build_mcp_server(config, registry)

    async with create_connected_server_and_client_session(server) as client:
        tools_result = await client.list_tools()
        names = {tool.name for tool in tools_result.tools}
        assert "bigquery_query" in names
        assert "data_quality_check" in names


@pytest.mark.anyio
async def test_call_tool_executes_allowed_query_over_mcp_protocol() -> None:
    registry, config = _build_registry()
    server = build_mcp_server(config, registry)

    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(
            "bigquery_query", {"sql": "SELECT * FROM `proj.sales.orders`"}
        )
        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        assert payload["rows"] == [{"id": 1, "amount": 9.99}]


@pytest.mark.anyio
async def test_call_tool_denied_query_returns_error_payload_not_exception() -> None:
    registry, config = _build_registry()
    server = build_mcp_server(config, registry)

    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(
            "bigquery_query", {"sql": "SELECT * FROM `proj.hr.salaries`"}
        )
        payload = json.loads(result.content[0].text)
        assert "error" in payload
        assert "allow-list" in payload["error"]
