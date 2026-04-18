# JSON / Markdown Schemas

Every workspace artifact has a defined shape. Scripts and sub-agents treat these as contracts.

## `spec.json`

Written by `requirements-interviewer`.

```json
{
  "version": "1.0",
  "goal": "string (≤200 chars)",
  "domain": "string",
  "user_persona": "string",
  "primary_trigger_phrases": ["string", "..."],
  "sub_tasks": [
    {
      "id": "kebab-case",
      "description": "string",
      "determinism_critical": false
    }
  ],
  "external_systems": [
    {
      "name": "string",
      "existing_mcp": "string | null",
      "read_or_write": "read|write|both"
    }
  ],
  "constraints": {
    "latency_budget_seconds": 0,
    "cost_sensitivity": "low|medium|high",
    "privacy": ["string"],
    "autonomy_limits": ["string"]
  },
  "success_criteria": ["string"],
  "assumptions": ["string"]
}
```

## `plan.md`

Written by the orchestrator in Phase 2. Plain markdown but **must** contain a fenced `plan` code block with this YAML:

````markdown
# Ecosystem Plan: <name>

**Pattern**: orchestrator-workers | sequential-pipeline | routing | parallelization-voting | evaluator-optimizer
**Rationale**: <one-sentence justification tied to spec.json>

```plan
name: ecosystem-name
description: one-line pushy description
pattern: orchestrator-workers
orchestrator:
  kind: command            # "command" or "skill"
  name: review-pr
  entry_file: commands/review-pr.md
agents:
  - name: security-reviewer
    role: reviews diff for security issues
    tools: [Read, Grep, Bash]
    model: sonnet
    description: >
      Reviews pull request diffs for security vulnerabilities (SQL injection, XSS,
      secrets, insecure auth). Use PROACTIVELY whenever a diff is visible or the
      user asks to check security of a PR or change.
skills:
  - name: pr-conventions
    trigger: user says "follow PR convention" or when writing PR body
    has_scripts: false
    has_references: true
mcps:
  - name: github
    mode: referenced                     # "referenced" or "custom"
    server: '@modelcontextprotocol/server-github'   # for referenced
  - name: internal-logs
    mode: custom                         # for custom
    language: python-fastmcp             # or "typescript-sdk"
    tools:
      - name: fetch_log
        input_schema: {run_id: string}
        description: Fetch a single log entry by run id.
hooks:
  - event: PostToolUse
    matcher: Edit|Write
    purpose: auto-format
```
````

The YAML inside the `plan` fenced block is the machine-readable contract `scaffold_plugin.py` and `scaffold_project.py` consume. The surrounding prose is for human review at the checkpoint.

## `target.json`

Written by the orchestrator in Phase 3.

```json
{
  "mode": "plugin" | "project",
  "output_path": "/absolute/path"
}
```

## `build-log.json`

Written by `ecosystem-builder` at end of Phase 4.

```json
{
  "iteration": 1,
  "files": [
    {"path": "agents/security-reviewer.md", "action": "create", "bytes": 1843}
  ],
  "warnings": ["string"]
}
```

## `validation.json`

Written by `ecosystem-validator` at end of Phase 5.

```json
{
  "status": "pass" | "fail",
  "score": 0.92,
  "iteration": 1,
  "rules": [
    {
      "id": "pushy-ness",
      "severity": "error|warning|info",
      "passed": true,
      "details": "string",
      "primitive": "agents/security-reviewer.md"
    }
  ],
  "fix_hints": [
    {
      "rule": "overlap-tokens",
      "primitive": "agents/code-auditor.md",
      "suggestion": "Rename to infra-auditor; narrow description to infrastructure/Terraform only."
    }
  ]
}
```

## Rule catalog (for validator)

| Rule id | Severity | Description |
|---|---|---|
| `schema-parse` | error | YAML frontmatter parses; required fields present. |
| `pushy-ness` | error | Description includes explicit trigger cue ("Use when", "Use PROACTIVELY"), third-person, 150–1024 chars. |
| `overlap-tokens` | error | Pairwise token Jaccard between agent descriptions ≤ 0.6. |
| `coverage` | warning | Every `spec.json.sub_tasks[].id` maps to ≥1 primitive (agent/skill/hook). |
| `orchestrator-references-workers` | error | Orchestrator command body mentions every worker agent name at least once. |
| `mcp-wiring` | error | Every custom MCP has `.mcp.json` entry; every `.mcp.json` entry references a real server or a scaffolded local path. |
| `tool-allowlist-sane` | error | Agents with `Bash` have a justification sentence; no `permissionMode: bypassPermissions`. |
| `trigger-eval-firerate` | error | Each primitive's intended triggers fire ≥0.7 of the time. |
| `semantic-overlap-judgment` | warning | (validator judgment) semantic overlap not caught by token Jaccard. |
| `pattern-fit-judgment` | warning | (validator judgment) chosen pattern fits the spec. |
| `skill-section-completeness` | warning | SKILL.md has Purpose, When to use, Workflow, Inputs, Outputs, Examples sections. |
