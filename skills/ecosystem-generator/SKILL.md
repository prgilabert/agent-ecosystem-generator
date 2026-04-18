---
name: ecosystem-generator
description: Scaffolds and validates a Claude Code ecosystem — one orchestrator command, N sub-agents, M skills, and custom or referenced MCPs — from a brief. Use when the user asks to design, scaffold, bootstrap, or plan a multi-agent system, agent team, agent orchestrator, or multi-skill plugin. Covers both portable-plugin and in-project .claude/ output modes.
---

# Ecosystem Generator

A skill that guides generation of a coordinated **orchestrator + N sub-agents + M skills + MCPs** ecosystem. Mirrors the `/generate-ecosystem` slash command so the model auto-triggers when users describe the intent without typing the command.

## Purpose

Turn a short brief like *"I want a PR review system with three checkers"* into a validated ecosystem ready to install (as a plugin) or commit (into `.claude/`).

## When to use

Fire this skill when the user says any of:
- "design a multi-agent system" / "agent team" / "agent orchestrator"
- "scaffold a plugin with N agents" / "bootstrap an orchestrator"
- "create a set of skills that work together"
- "I need a claude code setup that does X and Y and Z"
- "plan a Claude ecosystem for <domain>"

Do **not** fire this skill for single-skill generation — defer to `skill-creator` instead. If the user explicitly mentions only one agent or only one skill, this is not the right tool.

## Workflow

The skill runs the same 6 phases as the orchestrator command. Read `commands/generate-ecosystem.md` at `${CLAUDE_PLUGIN_ROOT}/commands/generate-ecosystem.md` for the canonical flow. The steps:

1. **Workspace bootstrap** — `scripts/init_workspace.py` creates a timestamped workspace dir.
2. **Requirements interview** — delegate to the `requirements-interviewer` sub-agent; read the resulting `spec.json`.
3. **Architecture** — read `references/orchestration-patterns.md` and pick a pattern; enumerate agents/skills/MCPs; write `plan.md` using the schema in `references/schemas.md`. Checkpoint with the user.
4. **Target pick** — ask the user: portable plugin vs. in-project `.claude/`.
5. **Build** — delegate to `ecosystem-builder` sub-agent, which uses `scripts/scaffold_plugin.py` or `scripts/scaffold_project.py` + `scripts/scaffold_mcp.py`.
6. **Validate** — delegate to `ecosystem-validator` sub-agent, which runs `scripts/validate_ecosystem.py` + `scripts/eval_triggers.py`. Iterate with the builder up to 3 rounds on failure.
7. **Summary** — report paths, file counts by primitive, validation score, install/activation next step.

## Inputs

- `user_brief` (string, optional) — free text.
- `cwd` — current working directory (for project-mode target).

## Outputs

- `<workspace>/spec.json` — captured requirements.
- `<workspace>/plan.md` — architectural plan.
- `<workspace>/target.json` — mode + output path.
- `<workspace>/build-log.json` — per iteration.
- `<workspace>/validation.json` — per iteration.
- `<output_path>/...` — the actual ecosystem (plugin or `.claude/` tree).

## Examples

**Example 1 — PR review ecosystem**

User: *"I want a Claude Code plugin that reviews PRs with three checkers: security, performance, tests. Orchestrated."*

Expected result:
- `spec.json`: 3 sub_tasks (security/performance/tests), external_systems = github (existing MCP).
- `plan.md`: pattern = orchestrator-workers; 1 command `/review-pr`, 3 agents (`security-reviewer`, `performance-reviewer`, `test-reviewer`), 0 custom MCPs, references `github` MCP.
- Validator: all 8 rules pass, firerate ≥0.7 per agent.

**Example 2 — Data pipeline monitor**

User: *"Monitor our ingestion pipeline: read logs from S3, classify errors, post to Slack. I don't think there's an MCP for our custom log format."*

Expected result:
- `spec.json`: 3 sub_tasks (fetch/classify/notify), external_systems = S3 + Slack + internal log format (no MCP).
- `plan.md`: pattern = sequential pipeline; 1 command `/monitor-pipeline`, 2 agents (`log-classifier`, `slack-notifier`), 1 skill `log-format-parser`, 1 **custom** FastMCP `internal-logs` with 2 tools (`fetch_log`, `summarize_window`), references `aws-s3` + `slack` MCPs.
- Validator: confirms MCP wiring; flags agent count as sanity-checked against sub_tasks count.

## Bundled resources

### References (read on demand)
- `references/schemas.md` — JSON shapes for `spec.json`, `plan.md`, `validation.json`, `build-log.json`.
- `references/frontmatter-patterns.md` — how to write pushy, third-person descriptions that trigger reliably.
- `references/orchestration-patterns.md` — 5 canonical patterns + when to pick each.
- `references/mcp-templates.md` — when to reference existing MCPs vs. scaffold custom ones; decision matrix.

### Assets (copy-filled into outputs)
- `assets/plugin-template/` — skeleton tree for portable plugin mode.
- `assets/project-config-template/` — skeleton tree for `.claude/` mode.
- `assets/mcp-stdio-template/python-fastmcp/` — FastMCP scaffold.
- `assets/mcp-stdio-template/typescript-sdk/` — `@modelcontextprotocol/sdk` scaffold.

### Scripts (deterministic steps — always prefer these over re-implementing)
- `scripts/init_workspace.py` — create the per-run workspace.
- `scripts/scaffold_plugin.py` — stamp plugin-mode output from `plan.md`.
- `scripts/scaffold_project.py` — stamp project-mode output from `plan.md`.
- `scripts/scaffold_mcp.py` — stamp a custom MCP (Python or TS).
- `scripts/validate_ecosystem.py` — structural + semantic validation.
- `scripts/eval_triggers.py` — trigger firerate evals.
- `scripts/utils.py` — shared helpers (frontmatter parsing, file I/O).

## Anti-patterns

- Do not write agents for every sub_task 1:1. Some sub_tasks are better expressed as **skills** (no context isolation needed, auto-trigger) or **hooks** (deterministic enforcement). Read `references/orchestration-patterns.md` §"Primitive choice" before the builder runs.
- Do not add a custom MCP when a CLI tool would do. Custom MCPs cost maintenance; a `Bash(gh:*)` allowlist often suffices.
- Do not skip the validator even if the build "looks right". Triggering is what makes or breaks an ecosystem in practice, and triggering is exactly what descriptions determine.
