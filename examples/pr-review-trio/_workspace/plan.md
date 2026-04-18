# Ecosystem Plan: pr-review-trio

**Pattern**: orchestrator-workers
**Rationale**: spec.json lists 3 independent checkers (security / performance / tests) that can run in parallel and whose outputs aggregate into a single PR-review comment.

```plan
name: pr-review-trio
description: Reviews pull requests with three independent checkers (security, performance, tests) and aggregates findings into a single structured comment. Use when the user says "review PR", "audit diff", or "ship this", or whenever a GitHub PR URL is pasted. Does NOT modify code — it only reports findings.
pattern: orchestrator-workers
pattern_rationale: spec.json lists 3 independent sub-tasks that can run in parallel.
orchestrator:
  kind: command
  name: review-pr
  body_intro: Orchestrates three parallel reviewers and aggregates their findings into one markdown report.
  argument_hint: "[PR number or URL]"
  allowed_tools: "Agent, Read, Bash(gh:*), Grep, Glob"
agents:
  - name: security-reviewer
    role: Scans the diff for security vulnerabilities.
    tools: [Read, Grep, Bash]
    model: sonnet
    description: >
      Reviews pull request diffs for security vulnerabilities including SQL injection, XSS,
      leaked secrets, insecure authentication flows, and missing input validation. Use
      PROACTIVELY whenever a diff is visible or the user asks to check security, audit a PR,
      or scan for secrets. Bash is needed because it runs gh pr diff. Does NOT cover
      performance or test coverage.
    workflow: |
      1. Run `gh pr diff $PR` to fetch the diff.
      2. Walk each hunk looking for known anti-patterns.
      3. Emit findings as a JSON array with {file, line, severity, rationale}.
    guardrails: |
      - Do not modify any files.
      - Do not call `gh pr merge` or `gh pr close`.
  - name: performance-reviewer
    role: Scans the diff for performance red flags.
    tools: [Read, Grep, Bash]
    model: sonnet
    description: >
      Reviews pull request diffs for performance problems: N+1 query patterns, unnecessary
      loops, allocation hotspots, blocking calls in async paths, missing indexes on new
      queries. Use PROACTIVELY on diffs or when the user says "perf check", "any N+1 here",
      or "is this hot path slow". Bash is needed because it runs gh pr diff. Does NOT cover
      security or test coverage.
    workflow: |
      1. Fetch diff via gh.
      2. Identify loops, queries, async/await sites.
      3. Emit findings as JSON array.
  - name: test-reviewer
    role: Verifies test coverage for the diff.
    tools: [Read, Grep, Bash]
    model: sonnet
    description: >
      Checks that every changed source module has a corresponding test touching the new
      behaviour. Use PROACTIVELY on diffs and whenever the user asks "is this tested",
      "do we have coverage", or "missing tests". Bash is needed because it runs gh pr diff
      and rg. Does NOT cover security or performance review.
    workflow: |
      1. Fetch diff.
      2. For each changed non-test file, search for a matching test file modification.
      3. Emit {file, has_test_change, matching_test_path}.
skills:
  - name: pr-comment-formatter
    description: >
      Formats aggregated reviewer findings into a single structured PR comment with collapsed
      sections per checker, severity icons, and a top summary. Use when aggregating security,
      performance, or test findings for a PR, or when the orchestrator assembles a final
      report. Does NOT fetch diffs or call the GitHub API — that is the orchestrator's job.
    purpose: Turn a list of findings into a reviewer-friendly markdown comment.
    when_to_use: After all three checkers return. Before the orchestrator posts a comment.
    workflow: |
      1. Group findings by checker.
      2. Sort by severity.
      3. Render markdown with `<details>` sections per checker.
    inputs: Array of findings objects.
    outputs: Markdown string ready to paste as a PR comment.
    examples: See assets/examples/.
mcps:
  - name: github
    mode: referenced
    server: "@modelcontextprotocol/server-github"
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"
hooks: []
```
