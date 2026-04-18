"""Scaffold a portable plugin directory from plan.md."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# add this script dir to path so sibling modules resolve when invoked by absolute path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scaffold_common import (
    load_workspace,
    render_agent,
    render_hooks_json,
    render_mcp_json,
    render_orchestrator,
    render_plugin_manifest,
    render_readme,
    render_skill,
)
from utils import write_file


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--author-name", default="Generated")
    ap.add_argument("--author-email", default="noreply@example.com")
    args = ap.parse_args()

    workspace = Path(args.workspace).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    plan, _target = load_workspace(workspace)
    files: list[dict] = []
    warnings: list[str] = []

    # plugin.json
    files.append(_emit(
        output / ".claude-plugin" / "plugin.json",
        render_plugin_manifest(plan, args.author_name, args.author_email),
    ))

    # README
    files.append(_emit(output / "README.md", render_readme(plan)))

    # Orchestrator command
    orch = plan["orchestrator"]
    orch_file = output / "commands" / f"{orch['name']}.md"
    files.append(_emit(orch_file, render_orchestrator(plan)))

    # Agents
    for agent in plan["agents"]:
        files.append(_emit(output / "agents" / f"{agent['name']}.md", render_agent(agent)))

    # Skills
    for skill in plan["skills"]:
        files.append(_emit(output / "skills" / skill["name"] / "SKILL.md", render_skill(skill)))

    # MCPs
    if plan["mcps"]:
        files.append(_emit(output / ".mcp.json", render_mcp_json(plan, output, mode="plugin")))
        for mcp in plan["mcps"]:
            if mcp["mode"] == "custom":
                files.extend(_scaffold_mcp(mcp, output / "mcps" / mcp["name"]))

    # Hooks
    hooks_rendered = render_hooks_json(plan)
    if hooks_rendered:
        files.append(_emit(output / "hooks" / "hooks.json", hooks_rendered))

    # Build log
    iteration = _next_iteration(workspace)
    build_log = {
        "iteration": iteration,
        "mode": "plugin",
        "output_path": str(output),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "files": files,
        "warnings": warnings,
    }
    (workspace / "build-log.json").write_text(
        json.dumps(build_log, indent=2), encoding="utf-8"
    )
    print(json.dumps(build_log, indent=2))


def _emit(path: Path, content: str) -> dict:
    bytes_ = write_file(path, content)
    return {"path": str(path), "action": "create", "bytes": bytes_}


def _scaffold_mcp(mcp: dict, mcp_dir: Path) -> list[dict]:
    from scaffold_mcp import scaffold_mcp

    return scaffold_mcp(mcp, mcp_dir)


def _next_iteration(workspace: Path) -> int:
    log_path = workspace / "build-log.json"
    if not log_path.exists():
        return 1
    try:
        prev = json.loads(log_path.read_text(encoding="utf-8"))
        return int(prev.get("iteration", 0)) + 1
    except Exception:
        return 1


if __name__ == "__main__":
    main()
