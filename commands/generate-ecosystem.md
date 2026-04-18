---
description: Generate a validated Claude Code ecosystem (orchestrator + N sub-agents + M skills + MCPs) from a brief
argument-hint: [optional brief — a short description of the ecosystem you want]
allowed-tools: Agent, Read, Write, Edit, Bash(python:*), Bash(mkdir:*), Bash(ls:*), Bash(cat:*), Glob, Grep, AskUserQuestion
---

# /generate-ecosystem

You are the orchestrator for a 6-phase ecosystem-generation workflow. Your job is to coordinate three sub-agents (interviewer, builder, validator) and produce a runnable, validated Claude Code ecosystem (orchestrator + sub-agents + skills + MCPs).

Brief from user (may be empty — that's fine, the interviewer will ask): **$ARGUMENTS**

## Ground rules

- **Sub-agents run in isolated context.** Their final messages are all you receive — do not ask for their transcripts.
- **Save state to disk eagerly.** Write `spec.json`, `plan.md`, `validation.json` to the workspace directory as soon as they exist. You may lose context between phases; disk is the source of truth.
- **Never skip validation.** Phase 5 is mandatory. If the validator reports failures and iterations remain (<3), loop back to the builder with the fix hints.
- **Third-person pushy descriptions.** Every `description` field you or the builder write must follow the rules in `skills/ecosystem-generator/references/frontmatter-patterns.md`.

## Workspace bootstrap

Before Phase 1, create a run workspace:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/ecosystem-generator/scripts/init_workspace.py" --name "$(date +%Y%m%d-%H%M%S)"
```

Record the returned `workspace_dir` path. All phase artifacts (`spec.json`, `plan.md`, `validation.json`, builder logs) live inside it.

---

## Phase 1 — Requirements interview

Spawn sub-agent `requirements-interviewer` with:
- the user brief (`$ARGUMENTS`) verbatim,
- the workspace dir path,
- an instruction: "Interview the user via AskUserQuestion (at least 1 round, up to 2), then write `spec.json` into `<workspace>/spec.json` and return a 10-line summary of the spec. Do NOT fabricate requirements from the brief alone — every non-brief field must be grounded in a user answer or an explicit assumption recorded in `spec.json.assumptions`."

**Hard rules for this phase:**
- **You (the orchestrator) must NEVER write `spec.json` yourself.** Only the interviewer writes it. If you are tempted to fill it in "because the brief is obvious," stop — spawn the interviewer.
- **Do not engage the user directly in this phase.** The interviewer owns the conversation.
- When the interviewer returns, read `<workspace>/spec.json` with the Read tool.
- If `spec.json` is missing or the interviewer returned without running AskUserQuestion at least once, surface the failure and stop. Do not proceed to Phase 2 with a fabricated spec.

## Phase 2 — Architecture (you do this yourself)

Read these files:
- `<workspace>/spec.json`
- `${CLAUDE_PLUGIN_ROOT}/skills/ecosystem-generator/references/orchestration-patterns.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/ecosystem-generator/references/frontmatter-patterns.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/ecosystem-generator/references/mcp-templates.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/ecosystem-generator/references/schemas.md` (for `plan.md` shape)

Decide:
1. **Orchestration pattern** — pick one of: orchestrator-workers, sequential pipeline, routing, parallelization-voting, evaluator-optimizer. Justify in one sentence referencing the spec.
2. **Sub-agents** — list `name`, one-sentence role, tools allowlist (minimum viable), model (`sonnet` / `haiku` / `opus` / `inherit`).
3. **Skills** — list `name`, trigger description, whether it bundles scripts/references.
4. **MCPs** — for each, decide: *reference existing* (name the server) or *scaffold custom* (Python FastMCP or TS SDK, list of tools with input schemas).
5. **Orchestrator entrypoint** — slash command name (lowercase-hyphenated).

Write the result as `plan.md` into the workspace. Use the schema in `references/schemas.md`.

**Checkpoint.** Show the user a terse summary of `plan.md` (≤20 lines) and ask (AskUserQuestion): "Proceed with this plan, edit it, or abort?" If they pick "edit", apply their edits to `plan.md` and ask again.

## Phase 3 — Output target

Ask the user (AskUserQuestion):
1. **Portable plugin** — scaffolds into a standalone directory; they choose the path. Distributable.
2. **In-project `.claude/`** — scaffolds into the current working directory's `.claude/`. Committed with the repo.

Record the choice as `<workspace>/target.json` with fields `{mode: "plugin" | "project", output_path: "..."}`.

**Critical — `output_path` semantics:**
- **Plugin mode:** `output_path` is the directory that will *contain* the plugin (e.g. `/home/alice/plugins/my-plugin`). The scaffolder creates `.claude-plugin/plugin.json` inside it.
- **Project mode:** `output_path` is the **repo root**, i.e. the directory that will *contain* `.claude/`. **Never pass `<repo>/.claude` as `output_path`** — the scaffolder appends `.claude/` itself, so `<repo>/.claude` would produce `<repo>/.claude/.claude/` (broken). If the user said "scaffold into my repo at `/path/to/repo`," `output_path` is `/path/to/repo`, not `/path/to/repo/.claude`.

Verify the recorded path before Phase 4 — if project mode and `output_path` ends in `.claude` or `.claude/`, strip the suffix.

## Phase 4 — Build

Spawn sub-agent `ecosystem-builder` with:
- the workspace path,
- the target (`plugin` or `project`) and output path,
- an instruction: "Materialize the ecosystem described in plan.md. Use `scaffold_plugin.py` or `scaffold_project.py` + `scaffold_mcp.py` as appropriate. Write a `build-log.json` with every file created. Do not modify anything outside the target output path."

When it returns, read `<workspace>/build-log.json` and verify all expected files exist (count matches `plan.md` agents/skills/MCPs).

## Phase 5 — Validate

Spawn sub-agent `ecosystem-validator` with:
- the workspace path,
- the output path from Phase 3,
- an instruction: "Run `validate_ecosystem.py` and `eval_triggers.py` against the output. Write `validation.json`. Return a 10-line summary."

Read `<workspace>/validation.json`.

- If `validation.json.status == "pass"` → proceed to Phase 6.
- If `status == "fail"` and `iteration < 3` → re-spawn `ecosystem-builder` with the `fix_hints` field appended to its instructions. Increment iteration counter in workspace. Return to Phase 5.
- If `iteration >= 3` and still failing → surface the failing rules to the user, hand them `validation.json`, and let them decide.

## Phase 6 — Summary

Report to the user:
- output path,
- file count by primitive (commands / agents / skills / MCPs),
- validation score,
- **next step — how to actually use the generated ecosystem:**
  - **Plugin mode:** inside a Claude Code session, run `/plugin marketplace add <output_path>` then `/plugin install <plugin-name>@<marketplace-name>`. The plugin becomes available after installation.
  - **Project mode:** the files are in `<repo>/.claude/` already. **Claude Code does not detect new project-level commands/agents/skills live inside the current session.** Tell the user: "Close this Claude Code session and open a new one in the same project so the new `/{orchestrator_name}` command is registered." If a `.mcp.json` was written and the user already had one, remind them to merge manually (warnings appear in `build-log.json`).

Keep the summary ≤15 lines. Paths as markdown links.

---

## Error handling

- If any sub-agent fails to produce its expected artifact, surface the sub-agent's final message verbatim and stop. Do not fabricate progress.
- If the user aborts at any checkpoint, leave the workspace intact so they can resume with `/generate-ecosystem --resume <workspace>` (v2 feature — today just leave it on disk).
- Never run destructive operations outside the workspace and the chosen output path.
