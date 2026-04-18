"""
{{mcp_name}} — custom stdio MCP server.

IMPORTANT: all logs must go to stderr. stdout is the JSON-RPC channel.
"""
import logging
import sys

from mcp.server.fastmcp import FastMCP

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
log = logging.getLogger("{{mcp_name}}")

mcp = FastMCP("{{mcp_name}}")

{{tool_definitions}}


def main() -> None:
    log.info("starting {{mcp_name}}")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
