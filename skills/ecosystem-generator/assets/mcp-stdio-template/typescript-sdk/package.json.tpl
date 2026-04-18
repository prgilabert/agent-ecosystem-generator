{
  "name": "{{mcp_name}}",
  "version": "0.1.0",
  "description": "{{mcp_description}}",
  "type": "module",
  "bin": {
    "{{mcp_name}}": "dist/server.js"
  },
  "scripts": {
    "build": "tsc",
    "start": "tsx src/server.ts",
    "test:inspect": "npx @modelcontextprotocol/inspector tsx src/server.ts"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.0.0",
    "zod": "^3.23.0"
  },
  "devDependencies": {
    "tsx": "^4.7.0",
    "typescript": "^5.4.0"
  }
}
