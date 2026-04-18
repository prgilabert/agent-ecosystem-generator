"""Scaffold an in-project .claude/ tree from plan.md."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scaffold_common import (
    load_workspace,
    render_agent,
    render_hooks_json,
    render_mcp_json,
    render_orchestrator,
    render_skill,
)
from utils import write_file


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--output", required=True, help="project root; .claude/ is created inside")
    args = ap.parse_args()

    workspace = Path(args.workspace).resolve()
    project_root = Path(args.output).resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    claude_dir = project_root / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    plan, _target = load_workspace(workspace)
    files: list[dict] = []
    warnings: list[str] = []

    # Orchestrator command → .claude/commands/
    orch = plan["orchestrator"]
    files.append(_emit(
        claude_dir / "commands" / f"{orch['name']}.md",
        render_orchestrator(plan),
    ))

    # Agents → .claude/agents/
    for agent in plan["agents"]:
        files.append(_emit(claude_dir / "agents" / f"{agent['name']}.md", render_agent(agent)))

    # Skills → .claude/skills/
    for skill in plan["skills"]:
        files.append(_emit(
            claude_dir / "skills" / skill["name"] / "SKILL.md",
            render_skill(skill),
        ))

    # .mcp.json → repo root (merged write — we don't merge yet, we overwrite with a warning)
    if plan["mcps"]:
        mcp_path = project_root / ".mcp.json"
        if mcp_path.exists():
            warnings.append(f"{mcp_path} already existed; overwrote. Merge manually if you had other servers.")
        files.append(_emit(mcp_path, render_mcp_json(plan, project_root, mode="project")))
        for mcp in plan["mcps"]:
            if mcp["mode"] == "custom":
                files.extend(_scaffold_mcp(mcp, project_root / "mcps" / mcp["name"]))

    # Hooks → .claude/settings.json (hooks key) — for safety, write next to it as hooks.generated.json
    hooks_rendered = render_hooks_json(plan)
    if hooks_rendered:
        files.append(_emit(claude_dir / "hooks.generated.json", hooks_rendered))
        warnings.append(
            ".claude/hooks.generated.json was written. Merge its `hooks` object into .claude/settings.json manually."
        )

    iteration = _next_iteration(workspace)
    build_log = {
        "iteration": iteration,
        "mode": "project",
        "output_path": str(project_root),
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
