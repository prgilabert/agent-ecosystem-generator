# agent-ecosystem-generator

> **Status: alpha.** Core flow smoke-tested end-to-end on a synthetic brief. Project-mode and custom-MCP paths are present but less exercised. Issues and PRs welcome.

Claude Code plugin that scaffolds a validated **orchestrator + N sub-agents + M skills/MCPs** ecosystem from a brief — a step up from `skill-creator`, which only scaffolds a single skill.

## What it does

1. `/generate-ecosystem` spawns a **`requirements-interviewer`** sub-agent that talks to you in isolated context and produces a `spec.json`.
2. The orchestrator picks an orchestration pattern (orchestrator-workers, sequential pipeline, routing, parallelization-voting, evaluator-optimizer), enumerates agents/skills/MCPs, and writes `plan.md`.
3. You pick the output target: **portable plugin** or **in-project `.claude/` config**.
4. A **`ecosystem-builder`** sub-agent materializes the files (+ scaffolds custom stdio MCPs in Python/FastMCP or TS SDK when needed).
5. A **`ecosystem-validator`** sub-agent runs semantic validation (overlap detection, pushy-ness scoring, coverage, MCP wiring) and trigger evals adapted from `skill-creator`. If anything fails, it loops back with fix hints up to 3 rounds.

## Install

```bash
# Clone and install from a local path (simplest for v0.1 while Claude Code's
# plugin installer for git URLs stabilizes):
git clone https://github.com/prgilabert/agent-ecosystem-generator.git
claude plugin install ./agent-ecosystem-generator
```

## Usage

```
/generate-ecosystem review PRs with three checkers: security, performance, tests
```

Or just describe what you want — the `ecosystem-generator` skill auto-triggers on phrases like "design a multi-agent system", "build an agent team", "scaffold an orchestrator".

## Examples

See [`examples/`](./examples) for real ecosystems produced by this plugin. Each one is an installable Claude Code plugin you can inspect or `claude plugin install` directly.

- [`examples/pr-review-trio/`](./examples/pr-review-trio) — orchestrator-workers pattern: `/review-pr` orchestrates 3 parallel reviewers (security, performance, tests), aggregates via the `pr-comment-formatter` skill, references the `github` MCP.

## Improvements over `skill-creator`

| Feature | `skill-creator` | `agent-ecosystem-generator` |
|---|---|---|
| Single skill vs ecosystem | Single | Orchestrator + N agents + M skills + MCPs |
| Output targets | Skill dir | Portable plugin **or** `.claude/` project config |
| Custom MCP scaffolding | Referenced only | FastMCP (Python) **and** `@modelcontextprotocol/sdk` (TS) templates |
| Validation depth | YAML fields present | Overlap detection, pushy-ness scoring, coverage, MCP wiring, trigger evals |
| Orchestration pattern pick | N/A | Pattern library with justification (5 canonical patterns) |
| Context isolation | N/A | Interviewer + builder + validator all run in isolated sub-agent ctx |

See [stack_explanation.md](stack_explanation.md) §1–6 for the background.
