# Roadmap

`agent-ecosystem-generator` is at **v0.1.0** — the core scaffolding,
validation, and trigger-eval pipeline works, but not every code path has
been exercised in a real Claude Code session. This roadmap is honest
about what's verified, what's planned, and where help is most welcome.

## Current state

| Capability | Status |
|---|---|
| Plugin manifest + slash command + sub-agents + skill | Complete |
| Orchestration-pattern library (5 patterns) | Complete |
| Plugin-mode scaffolder | Smoke-tested end-to-end |
| Project-mode scaffolder (`.claude/`) | Written, **not yet smoke-tested** |
| Custom MCP scaffolders (Python FastMCP + TypeScript SDK) | Written, **not yet smoke-tested** |
| Semantic validator (8 rules) | Working; example in repo passes at 0.94 |
| Trigger-firerate eval (offline proxy) | Working |
| `PostToolUse` hook quick-validate | Present; untested inside a real Claude Code session |

## Planned (contributions welcome)

### Prompt quality
- **Interviewer few-shots per domain.** The `requirements-interviewer`
  currently asks the same broad questions regardless of brief. Adding
  domain-specific few-shots (PR review, data pipeline, MCP-heavy,
  routing) would make the interview adapt.
- **Pattern-picker decision table.** In Phase 2 of `/generate-ecosystem`,
  the orchestrator picks an orchestration pattern. A hard-coded decision
  table ("N independent tasks → orchestrator-workers; N ordered steps →
  pipeline; classification → routing") would reduce the default-to-
  workers bias and force a cited justification in `plan.md`.

### Validation
- **Embedding-based overlap.** The current `overlap-tokens` rule uses
  Jaccard; paraphrased descriptions slip through. Embeddings would catch
  them, behind a `--overlap-mode embeddings` flag.
- **Real-model trigger eval.** The current eval is a deterministic token-
  overlap proxy. A `--mode api` flag that calls Claude for routing
  judgment would give gold-standard firerate, with the proxy kept as
  zero-dep default.

### Testing / infra
- **pytest harness.** The smoke test is manual (see `examples/README.md`
  for the reproducer). Moving it to `tests/` with golden fixtures would
  lock regressions in CI.
- **GitHub Actions.** Run the harness on every PR.

### Examples
- More patterns: pipeline, routing, parallelization-voting, evaluator-
  optimizer. Each should ship with its `spec.json` / `plan.md` /
  `validation.json` for traceability.
- At least one ecosystem that **scaffolds a custom MCP** end-to-end.

## Not yet verified (you may hit bugs)

- `claude plugin install` on a fresh Claude Code session.
- `/generate-ecosystem` as a full interactive flow — only the scripts
  under `skills/ecosystem-generator/scripts/` have been end-to-end tested.
  The three sub-agents' prompts haven't been executed against a real
  model-served session.
- Project-mode output landing cleanly in a repo with pre-existing
  `.mcp.json` or `.claude/hooks.json`.
- Custom MCPs arriving with working tool implementations. The templates
  stamp files; they don't test the generated server actually runs.

## How to help

**Low-effort (great first PR):**
- Try `claude plugin install` and report failures in issues.
- Submit a new example under `examples/` (see `examples/README.md`).
- Fix a typo, tighten a description, improve an agent prompt.

**Medium:**
- Add `--mode api` to `scripts/eval_triggers.py`.
- Write the first `tests/test_validate.py` against known-good and
  known-bad primitives.
- Port the `requirements-interviewer` prompt to include domain-specific
  few-shots.

**Larger:**
- Replace the Jaccard overlap rule with an embedding-based version.
- Wire up GitHub Actions with the pytest harness once it exists.

---

*Last updated at v0.1.0. This roadmap is a living document — PRs to edit
it (add, reorder, or strike items) are as welcome as PRs against the
code.*
