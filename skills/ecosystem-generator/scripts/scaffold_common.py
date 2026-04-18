"""Shared scaffolding for plugin-mode and project-mode outputs."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from utils import (
    ASSETS,
    plugin_root,
    render_template_file,
    write_file,
    yaml_quote,
)


def load_workspace(workspace: Path) -> tuple[dict, dict]:
    """Return (plan, target) dicts."""
    from utils import parse_plan  # lazy import to avoid circular

    plan_path = workspace / "plan.md"
    if not plan_path.exists():
        raise FileNotFoundError(f"{plan_path} not found — run Phase 2 first")
    plan = parse_plan(plan_path)

    target_path = workspace / "target.json"
    target = json.loads(target_path.read_text(encoding="utf-8")) if target_path.exists() else {}
    return plan, target


def render_orchestrator(plan: dict) -> str:
    orch = plan["orchestrator"]
    tpl = ASSETS / "plugin-template" / "commands" / "orchestrator.md.tpl"
    phases_body, workers_body = _pattern_phases(plan)
    context = {
        "orchestrator_name": orch["name"],
        "orchestrator_description": yaml_quote(plan.get("description", orch.get("description", ""))),
        "argument_hint": orch.get("argument_hint", "[optional brief]"),
        "allowed_tools": orch.get("allowed_tools", "Agent, Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion"),
        "orchestrator_body_intro": orch.get("body_intro", f"Orchestrator for the {plan['name']} ecosystem."),
        "pattern": plan["pattern"],
        "pattern_rationale": plan.get("pattern_rationale", ""),
        "phases_body": phases_body,
        "workers_body": workers_body,
    }
    return render_template_file(tpl, context)


def render_agent(agent: dict) -> str:
    tpl = ASSETS / "plugin-template" / "agents" / "agent.md.tpl"
    name = agent["name"]  # required — no sensible default
    description = agent.get("description") or f"Sub-agent {name}. TODO: add a third-person description starting with a verb."
    context = {
        "agent_name": name,
        "agent_description": yaml_quote(description),
        "agent_tools": _as_yaml_list(agent.get("tools", [])),
        "agent_model": agent.get("model", "sonnet"),
        "agent_role": agent.get("role", ""),
        "agent_inputs": agent.get("inputs", "Inputs are passed as parameters by the orchestrator."),
        "agent_workflow": agent.get("workflow", "1. Read the inputs.\n2. Perform the role.\n3. Return a concise summary."),
        "agent_output": agent.get("output", "A plain-text summary to the orchestrator."),
        "agent_guardrails": agent.get("guardrails", "- Do not modify files outside the provided output path.\n- Do not set `permissionMode: bypassPermissions`."),
    }
    return render_template_file(tpl, context)


def render_skill(skill: dict) -> str:
    tpl = ASSETS / "plugin-template" / "skills" / "SKILL.md.tpl"
    name = skill["name"]  # required — no sensible default
    description = skill.get("description") or f"Skill {name}. TODO: add a trigger-rich description starting with a verb."
    context = {
        "skill_name": name,
        "skill_title": skill.get("title", name.replace("-", " ").title()),
        "skill_description": yaml_quote(description),
        "skill_purpose": skill.get("purpose", ""),
        "skill_when_to_use": skill.get("when_to_use", skill.get("trigger", "")),
        "skill_workflow": skill.get("workflow", "Document the steps the skill walks through here."),
        "skill_inputs": skill.get("inputs", "Inputs the user or orchestrator provides."),
        "skill_outputs": skill.get("outputs", "Artifacts or responses produced."),
        "skill_examples": skill.get("examples", "Add 1–2 realistic invocation examples."),
    }
    return render_template_file(tpl, context)


def render_plugin_manifest(plan: dict, author_name: str, author_email: str) -> str:
    tpl = ASSETS / "plugin-template" / ".claude-plugin" / "plugin.json.tpl"
    context = {
        "name": plan["name"],
        "description": _json_escape(plan.get("description", "")),
        "author_name": author_name,
        "author_email": author_email,
        "keywords_json": json.dumps(plan.get("keywords", [])),
    }
    return render_template_file(tpl, context)


def render_readme(plan: dict) -> str:
    tpl = ASSETS / "plugin-template" / "README.md.tpl"
    orch = plan["orchestrator"]
    context = {
        "name": plan["name"],
        "description": plan.get("description", ""),
        "pattern": plan["pattern"],
        "pattern_rationale": plan.get("pattern_rationale", ""),
        "orchestrator_name": orch["name"],
        "agents_list": ", ".join(a["name"] for a in plan["agents"]) or "(none)",
        "skills_list": ", ".join(s["name"] for s in plan["skills"]) or "(none)",
        "mcps_list": ", ".join(f"{m['name']} ({m['mode']})" for m in plan["mcps"]) or "(none)",
        "generated_at": datetime.now().isoformat(timespec="minutes"),
    }
    return render_template_file(tpl, context)


def render_mcp_json(plan: dict, output_path: Path, mode: str) -> str:
    tpl = ASSETS / "plugin-template" / ".mcp.json.tpl"
    servers: dict[str, Any] = {}
    for mcp in plan["mcps"]:
        if mcp["mode"] == "referenced":
            servers[mcp["name"]] = {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", mcp.get("server", f"@modelcontextprotocol/server-{mcp['name']}")],
                "env": mcp.get("env", {}),
            }
        elif mcp["mode"] == "custom":
            rel = _custom_mcp_path(mcp, mode)
            if mcp.get("language") == "typescript-sdk":
                servers[mcp["name"]] = {
                    "type": "stdio",
                    "command": "npx",
                    "args": ["tsx", f"{rel}/src/server.ts"],
                }
            else:  # python-fastmcp default
                servers[mcp["name"]] = {
                    "type": "stdio",
                    "command": "python",
                    "args": [f"{rel}/server.py"],
                }
    context = {"mcp_servers_json": json.dumps(servers, indent=2)}
    return render_template_file(tpl, context)


def render_hooks_json(plan: dict) -> str | None:
    if not plan["hooks"]:
        return None
    tpl = ASSETS / "plugin-template" / "hooks" / "hooks.json.tpl"
    hooks_by_event: dict[str, list] = {}
    for h in plan["hooks"]:
        hooks_by_event.setdefault(h["event"], []).append(
            {"matcher": h.get("matcher", ""), "hooks": [{"type": "command", "command": h.get("command", "echo todo")}]}
        )
    context = {"hooks_json": json.dumps(hooks_by_event, indent=2)}
    return render_template_file(tpl, context)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_yaml_list(items: list[str]) -> str:
    if not items:
        return "[]"
    return "[" + ", ".join(items) + "]"


def _json_escape(s: str) -> str:
    """Escape a string for inclusion inside a JSON string literal."""
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _custom_mcp_path(mcp: dict, mode: str) -> str:
    if mode == "plugin":
        return f"${{CLAUDE_PLUGIN_ROOT}}/mcps/{mcp['name']}"
    return f"${{CLAUDE_PROJECT_DIR}}/mcps/{mcp['name']}"


def _pattern_phases(plan: dict) -> tuple[str, str]:
    pattern = plan["pattern"]
    agents = plan["agents"]

    if pattern == "orchestrator-workers":
        phases = "1. Read inputs from `$ARGUMENTS`.\n2. Spawn workers in parallel via the Agent tool.\n3. Aggregate worker outputs into a single response."
    elif pattern == "sequential-pipeline":
        phases = "\n".join(f"{i+1}. {a['name']} — {a.get('role','')}" for i, a in enumerate(agents))
    elif pattern == "routing":
        phases = "1. Classify the input.\n2. Route to exactly one specialist.\n3. Return that specialist's output."
    elif pattern == "parallelization-voting":
        phases = "1. Spawn N evaluators in parallel.\n2. Aggregate via majority or evaluator-LLM.\n3. Return the aggregated decision."
    elif pattern == "evaluator-optimizer":
        phases = "1. Generator produces a candidate.\n2. Evaluator scores against rubric.\n3. Loop until pass or max-iterations."
    else:
        phases = "1. (custom pattern — edit this section)"

    workers = "\n".join(f"- `{a['name']}` — {a.get('role','')}" for a in agents) or "(no workers)"
    return phases, workers
