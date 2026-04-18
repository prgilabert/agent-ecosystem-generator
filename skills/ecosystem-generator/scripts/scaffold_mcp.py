"""Scaffold a single custom stdio MCP server (Python FastMCP or TypeScript SDK)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import ASSETS, render_template_file, write_file


def scaffold_mcp(mcp: dict, out_dir: Path) -> list[dict]:
    """Stamp a custom MCP into out_dir. Returns the list of files written."""
    language = mcp.get("language", "python-fastmcp")
    if language not in ("python-fastmcp", "typescript-sdk"):
        raise ValueError(f"unsupported language: {language}")

    tpl_dir = ASSETS / "mcp-stdio-template" / language
    if language == "python-fastmcp":
        return _scaffold_python(mcp, tpl_dir, out_dir)
    return _scaffold_ts(mcp, tpl_dir, out_dir)


def _scaffold_python(mcp: dict, tpl_dir: Path, out_dir: Path) -> list[dict]:
    ctx = _common_ctx(mcp)
    ctx["mcp_module"] = mcp["name"].replace("-", "_")
    ctx["tool_definitions"] = _python_tools(mcp.get("tools", []))
    ctx["tools_table"] = _tools_table(mcp.get("tools", []))

    files: list[dict] = []
    files.append(_emit(out_dir / "server.py", render_template_file(tpl_dir / "server.py.tpl", ctx)))
    files.append(_emit(out_dir / "pyproject.toml", render_template_file(tpl_dir / "pyproject.toml.tpl", ctx)))
    files.append(_emit(out_dir / "README.md", render_template_file(tpl_dir / "README.md.tpl", ctx)))
    return files


def _scaffold_ts(mcp: dict, tpl_dir: Path, out_dir: Path) -> list[dict]:
    ctx = _common_ctx(mcp)
    ctx["tool_definitions"] = _ts_tools(mcp.get("tools", []))
    ctx["tools_table"] = _tools_table(mcp.get("tools", []))

    files: list[dict] = []
    files.append(_emit(out_dir / "src" / "server.ts", render_template_file(tpl_dir / "src" / "server.ts.tpl", ctx)))
    files.append(_emit(out_dir / "package.json", render_template_file(tpl_dir / "package.json.tpl", ctx)))
    files.append(_emit(out_dir / "tsconfig.json", render_template_file(tpl_dir / "tsconfig.json.tpl", ctx)))
    files.append(_emit(out_dir / "README.md", render_template_file(tpl_dir / "README.md.tpl", ctx)))
    return files


def _common_ctx(mcp: dict) -> dict:
    return {
        "mcp_name": mcp["name"],
        "mcp_description": mcp.get("description", f"Custom MCP server: {mcp['name']}"),
    }


def _python_tools(tools: list[dict]) -> str:
    lines: list[str] = []
    for t in tools:
        name = t["name"]
        desc = t.get("description", "").strip() or f"Tool {name}"
        schema = t.get("input_schema", {}) or {}
        params_src = ", ".join(f"{k}: {_py_type(v)}" for k, v in schema.items()) or ""
        lines.append(f'@mcp.tool()\ndef {name}({params_src}) -> str:\n    """{desc}"""\n    # TODO: implement\n    return ""\n')
    return "\n\n".join(lines) or "# (no tools declared in plan.md — add one by decorating a function with @mcp.tool())"


def _ts_tools(tools: list[dict]) -> str:
    lines: list[str] = []
    for t in tools:
        name = t["name"]
        desc = t.get("description", "").strip() or f"Tool {name}"
        schema = t.get("input_schema", {}) or {}
        zod_schema = "{ " + ", ".join(f"{k}: {_zod_type(v)}" for k, v in schema.items()) + " }"
        lines.append(
            f'server.registerTool("{name}",\n'
            f'  {{ title: "{name}", description: "{desc}",\n'
            f"    inputSchema: {zod_schema} }},\n"
            f"  async (args) => ({{ content: [{{ type: \"text\", text: JSON.stringify(args) }}] }})\n"
            f");"
        )
    return "\n\n".join(lines) or "// (no tools declared in plan.md — register one with server.registerTool)"


def _tools_table(tools: list[dict]) -> str:
    if not tools:
        return "_(none — add tools to plan.md)_"
    rows = ["| name | description | input |", "|---|---|---|"]
    for t in tools:
        schema = t.get("input_schema", {}) or {}
        input_str = ", ".join(f"{k}:{v}" for k, v in schema.items()) or "—"
        rows.append(f"| `{t['name']}` | {t.get('description', '').strip()} | `{input_str}` |")
    return "\n".join(rows)


_PY_TYPES = {"string": "str", "integer": "int", "number": "float", "boolean": "bool", "array": "list", "object": "dict"}


def _py_type(v: str) -> str:
    return _PY_TYPES.get(str(v).lower(), "str")


def _zod_type(v: str) -> str:
    mapping = {
        "string": "z.string()",
        "integer": "z.number().int()",
        "number": "z.number()",
        "boolean": "z.boolean()",
        "array": "z.array(z.any())",
        "object": "z.object({}).passthrough()",
    }
    return mapping.get(str(v).lower(), "z.string()")


def _emit(path: Path, content: str) -> dict:
    bytes_ = write_file(path, content)
    return {"path": str(path), "action": "create", "bytes": bytes_}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=False, help="unused; for API symmetry")
    ap.add_argument("--name", required=True)
    ap.add_argument("--language", choices=["python-fastmcp", "typescript-sdk"], default="python-fastmcp")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tools-json", default="[]", help='JSON array: [{"name":"x","description":"...","input_schema":{"id":"string"}}]')
    args = ap.parse_args()

    mcp = {
        "name": args.name,
        "language": args.language,
        "description": f"Custom stdio MCP server: {args.name}",
        "tools": json.loads(args.tools_json),
    }
    out = Path(args.out).resolve()
    files = scaffold_mcp(mcp, out)
    print(json.dumps({"files": files}, indent=2))


if __name__ == "__main__":
    main()
