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
- an instruction: "Write `spec.json` into `<workspace>/spec.json` and return a 10-line summary of the spec."

**Do not engage the user directly in this phase.** The interviewer owns the conversation. When it returns, read `<workspace>/spec.json` with the Read tool.

If `spec.json` is missing, stop and surface the failure.

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
- next step command:
  - plugin mode: `claude plugin install <output_path>`
  - project mode: verify `.claude/` is in the current repo; live detection surfaces the new primitives immediately.

Keep the summary ≤15 lines. Paths as markdown links.

---

## Error handling

- If any sub-agent fails to produce its expected artifact, surface the sub-agent's final message verbatim and stop. Do not fabricate progress.
- If the user aborts at any checkpoint, leave the workspace intact so they can resume with `/generate-ecosystem --resume <workspace>` (v2 feature — today just leave it on disk).
- Never run destructive operations outside the workspace and the chosen output path.
