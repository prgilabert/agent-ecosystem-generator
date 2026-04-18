# {{mcp_name}}

{{mcp_description}}

## Install

```bash
pip install -e .
```

## Run (stdio)

```bash
python server.py
```

## Test with inspector

```bash
npx @modelcontextprotocol/inspector python server.py
```

Opens a UI at `http://localhost:6274` where you can call each tool and inspect the JSON-RPC traffic.

## Tools

{{tools_table}}

## Logging

All logs go to stderr. stdout is reserved for the JSON-RPC protocol — writing to stdout would corrupt the channel.
