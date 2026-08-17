"""MCP server wiring: turns a validated :class:`AppConfig` into a running server."""

from mcp_data_tools.server.factory import build_tool_registry
from mcp_data_tools.server.mcp_server import build_mcp_server, serve_stdio

__all__ = ["build_mcp_server", "build_tool_registry", "serve_stdio"]
