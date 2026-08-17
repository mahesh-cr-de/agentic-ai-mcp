"""Wires a :class:`ToolRegistry` into an MCP ``Server`` instance."""

from __future__ import annotations

import json
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server

from mcp_data_tools import __version__
from mcp_data_tools.core.config import AppConfig
from mcp_data_tools.core.exceptions import McpDataToolsError
from mcp_data_tools.core.logging import get_logger
from mcp_data_tools.tools.registry import ToolRegistry

_LOGGER = get_logger(__name__)

#: Best-effort caller identity used for the audit trail until MCP exposes a
#: stable, per-session client identity through the protocol. Overridable via
#: the ``_actor`` field on a tool call's arguments (stripped before dispatch)
#: for callers that do have such an identity (e.g. a gateway that knows the
#: authenticated end user).
_DEFAULT_ACTOR = "mcp-client"


def build_mcp_server(config: AppConfig, registry: ToolRegistry) -> Server:
    """Construct an MCP ``Server`` that dispatches to ``registry``.

    Args:
        config: The application configuration (used for server metadata).
        registry: The tool registry built by
            :func:`mcp_data_tools.server.factory.build_tool_registry`.

    Returns:
        A configured, not-yet-running :class:`mcp.server.lowlevel.Server`.
    """
    server: Server = Server(
        name=config.server.name,
        version=__version__,
        instructions=config.server.instructions,
    )

    # The `mcp` SDK's Server.list_tools/call_tool decorators are not typed
    # precisely enough for mypy --strict to infer the wrapped function's
    # signature (a known gap in the upstream SDK's type stubs, not a bug in
    # this code) — the two ignores below are scoped to that single line each.
    @server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
    async def _list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=tool.name,
                description=tool.description,
                inputSchema=tool.input_schema,
            )
            for tool in registry.tools.values()
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        actor = str(arguments.pop("_actor", _DEFAULT_ACTOR))
        try:
            tool = registry.get(name)
            result = tool.execute(arguments, actor=actor)
        except McpDataToolsError as exc:
            _LOGGER.warning(
                "tool call failed",
                extra={"tool_name": name, "actor": actor, "error": exc.message},
            )
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": exc.message, "details": exc.details}),
                )
            ]
        return [types.TextContent(type="text", text=json.dumps(result, default=str))]

    return server


async def serve_stdio(config: AppConfig, registry: ToolRegistry) -> None:
    """Run the MCP server over stdio until the client disconnects.

    Args:
        config: The application configuration.
        registry: The tool registry to serve.
    """
    from mcp.server.stdio import stdio_server  # noqa: PLC0415

    server = build_mcp_server(config, registry)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


__all__ = ["build_mcp_server", "serve_stdio"]
