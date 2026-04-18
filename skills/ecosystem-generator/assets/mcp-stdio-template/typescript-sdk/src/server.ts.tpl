// {{mcp_name}} — custom stdio MCP server.
// IMPORTANT: all logs go to stderr via console.error. stdout is the JSON-RPC channel.

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer(
  { name: "{{mcp_name}}", version: "0.1.0" },
  { instructions: "{{mcp_description}}" }
);

{{tool_definitions}}

async function main(): Promise<void> {
  console.error("starting {{mcp_name}}");
  await server.connect(new StdioServerTransport());
}

main().catch((err) => {
  console.error("fatal:", err);
  process.exit(1);
});
