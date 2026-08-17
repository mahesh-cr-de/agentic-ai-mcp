"""Command-line entrypoint: ``mcp-data-tools serve --config <path>``."""

from __future__ import annotations

import argparse
import sys

import anyio

from mcp_data_tools import __version__
from mcp_data_tools.core.config import AppConfig
from mcp_data_tools.core.exceptions import McpDataToolsError
from mcp_data_tools.core.logging import configure_logging, get_logger
from mcp_data_tools.server.factory import build_tool_registry
from mcp_data_tools.server.mcp_server import serve_stdio

_LOGGER = get_logger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcp-data-tools")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Run the MCP server over stdio.")
    serve_parser.add_argument("--config", required=True, help="Path to a YAML/JSON config file.")
    serve_parser.add_argument(
        "--log-level",
        default=None,
        help="Override server.log_level from the config file.",
    )

    validate_parser = subparsers.add_parser(
        "validate-config", help="Validate a config file and exit."
    )
    validate_parser.add_argument("--config", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint.

    Args:
        argv: Argument vector, defaulting to ``sys.argv[1:]``.

    Returns:
        Process exit code (0 on success, 1 on a handled configuration or
        startup error).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        config = AppConfig.from_file(args.config)
    except McpDataToolsError as exc:
        print(f"Configuration error: {exc.message}", file=sys.stderr)
        return 1

    if args.command == "validate-config":
        enabled = len(config.server.enabled_tools) or "all"
        print(f"OK: {args.config} is valid ({enabled} tools enabled)")
        return 0

    log_level = args.log_level or config.server.log_level
    configure_logging(log_level, force=True)

    try:
        registry = build_tool_registry(config)
    except McpDataToolsError as exc:
        _LOGGER.error("startup failed", extra={"error": exc.message})
        return 1

    _LOGGER.info(
        "starting mcp-data-tools",
        extra={"version": __version__, "tools": sorted(registry.tools)},
    )
    anyio.run(serve_stdio, config, registry)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["main"]
