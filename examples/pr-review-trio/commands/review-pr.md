---
description: "Reviews pull requests with three independent checkers (security, performance, tests) and aggregates findings into a single structured comment. Use when the user says \"review PR\", \"audit diff\", or \"ship this\", or whenever a GitHub PR URL is pasted. Does NOT modify code — it only reports findings."
argument-hint: [PR number or URL]
allowed-tools: Agent, Read, Bash(gh:*), Grep, Glob
---

# /review-pr

Orchestrates three parallel reviewers and aggregates their findings into one markdown report.

Input: **$ARGUMENTS**

## Pattern: orchestrator-workers

spec.json lists 3 independent sub-tasks that can run in parallel.

## Phases

1. Read inputs from `$ARGUMENTS`.
2. Spawn workers in parallel via the Agent tool.
3. Aggregate worker outputs into a single response.

## Workers

- `security-reviewer` — Scans the diff for security vulnerabilities.
- `performance-reviewer` — Scans the diff for performance red flags.
- `test-reviewer` — Verifies test coverage for the diff.

## Error handling

If any worker returns without its expected artifact, surface its final message verbatim and stop. Do not fabricate progress.
