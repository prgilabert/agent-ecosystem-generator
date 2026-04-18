# MCP templates — reference vs. scaffold custom

MCPs are the biggest generator of context bloat in Claude Code today (documented 60–80k tokens before first prompt with 4 servers). Add them sparingly, and only when a CLI allowlist doesn't suffice.

## Decision matrix

```
Need external data?
├── No → don't add MCP
└── Yes
    ├── CLI tool exists (gh, aws, psql, sentry-cli)?
    │   └── Prefer Bash allowlist in the agent definition. Cheaper.
    └── No CLI, or data is structured and frequently queried
        ├── Existing MCP server covers it (github, postgres, filesystem, slack, stripe)?
        │   └── Reference it in .mcp.json — mode: "referenced"
        └── No existing server
            └── Scaffold custom stdio MCP — mode: "custom"
                ├── Python → FastMCP template
                └── TypeScript → @modelcontextprotocol/sdk template
```

## Known existing MCPs (reference first, don't re-implement)

| Need | Server | Transport |
|---|---|---|
| GitHub issues/PRs/repos | `@modelcontextprotocol/server-github` | stdio or HTTP |
| Postgres | `@bytebase/dbhub` | stdio |
| Filesystem (scoped) | `@modelcontextprotocol/server-filesystem` | stdio |
| Slack | `@modelcontextprotocol/server-slack` | stdio |
| Google Drive / Gmail / Calendar | plugin_design_* servers | HTTP |
| Linear | plugin_design_linear | HTTP |
| Atlassian | plugin_design_atlassian | HTTP |
| Stripe | via official connector | HTTP |
| Sentry | via `sentry-cli` (prefer CLI, not MCP) | — |

If in doubt: search `https://github.com/modelcontextprotocol/servers` before scaffolding.

## When to scaffold custom

Scaffold a custom stdio MCP when **all** of these hold:
- No existing server covers the need.
- The data is structured (not free-form files) and the agent will query it multiple times per session.
- The caller benefits from tool-shaped affordances (explicit input schema, typed output) rather than shell parsing.

Don't scaffold custom if:
- The need is one-shot (Bash `curl` is fine).
- The data is unstructured text files (the filesystem MCP suffices).
- The user doesn't own the backend (i.e. you'd be reverse-engineering someone else's API).

## Language pick

- **Python FastMCP** — default. Smallest scaffold (`@mcp.tool()` decorator), tight iteration loop. Use when the team is Python-native.
- **TypeScript SDK** — use when the MCP shares code with an existing TS codebase, or the tools must import existing TS types/schemas.

## Custom MCP quality gates (builder enforces)

When `scaffold_mcp.py` stamps a new server, it writes a `README.md` with:
- install instructions,
- run command,
- **test command**: `npx @modelcontextprotocol/inspector <run-cmd>` for stdio servers.

The generated `.mcp.json` entry points to the scaffolded path using relative path or `${VAR}` expansion, not absolute user paths.

## stdio gotchas the template already handles

- Logs to **stderr only** (stdout is the JSON-RPC channel). Python template imports `logging` configured to stderr; TS template uses `console.error`.
- No top-level `print()` — corrupts the protocol.
- `initialize` handshake already wired by FastMCP / SDK; no manual JSON-RPC.

## Referenced MCP entry shape in `.mcp.json`

```json
{
  "mcpServers": {
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"}
    }
  }
}
```

## Custom MCP entry shape in `.mcp.json`

```json
{
  "mcpServers": {
    "internal-logs": {
      "type": "stdio",
      "command": "python",
      "args": ["${CLAUDE_PROJECT_DIR}/mcps/internal-logs/server.py"]
    }
  }
}
```

## Validator rule `mcp-wiring`

Fails if:
- A custom MCP exists on disk but has no `.mcp.json` entry.
- A `.mcp.json` entry names a custom MCP whose path doesn't exist.
- A referenced MCP's server package name is malformed.
