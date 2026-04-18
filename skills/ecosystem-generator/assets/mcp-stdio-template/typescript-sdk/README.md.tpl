# {{mcp_name}}

{{mcp_description}}

## Install

```bash
npm install
```

## Run (stdio)

```bash
npm start
```

## Test with inspector

```bash
npm run test:inspect
```

Opens a UI at `http://localhost:6274` where you can call each tool and inspect the JSON-RPC traffic.

## Tools

{{tools_table}}

## Logging

All logs go to stderr via `console.error`. stdout is reserved for the JSON-RPC protocol — writing to stdout would corrupt the channel.
