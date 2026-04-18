# Examples

Reference ecosystems produced by `agent-ecosystem-generator`. Each subfolder is a **real, installable Claude Code plugin** that came out of the generator — not a hand-written mock.

Browse these before installing the generator yourself to see what `/generate-ecosystem` actually emits.

## Gallery

| Example | Pattern | Primitives | Validation | MCPs |
|---|---|---|---|---|
| [`pr-review-trio/`](./pr-review-trio) | orchestrator-workers | 1 command + 3 sub-agents + 1 skill | pass (0.94) | `github` (referenced) |

## Reading an example

Each example folder has two parts:

1. **The generated plugin** (top-level files + `.claude-plugin/`, `agents/`, `commands/`, `skills/`, `.mcp.json`). You can `claude plugin install ./examples/<name>` directly and it will work.
2. **`_workspace/`** — the inputs and validator output that produced the plugin. Not part of the installable plugin; kept so you can trace back "what brief → what spec → what plan → what output".
   - `spec.json` — output of the `requirements-interviewer` sub-agent (the structured requirements).
   - `plan.md` — the orchestrator's architecture decision (pattern, agents, skills, MCPs).
   - `validation.json` — the `ecosystem-validator`'s verdict across all 8 rules.

## How these examples were produced

The first example (`pr-review-trio`) was produced by running the scaffolding scripts directly with a hand-written `spec.json` + `plan.md`, bypassing the full `/generate-ecosystem` interactive flow. This gives deterministic, reproducible outputs for the gallery. The output is **byte-identical** to what the full flow would emit for the same plan.

If you want to reproduce it yourself:

```bash
cd agent-ecosystem-generator
python skills/ecosystem-generator/scripts/scaffold_plugin.py \
  --workspace examples/pr-review-trio/_workspace \
  --output /tmp/pr-review-trio-regen
python skills/ecosystem-generator/scripts/validate_ecosystem.py \
  --target /tmp/pr-review-trio-regen \
  --workspace examples/pr-review-trio/_workspace \
  --full
```

## Contributing examples

PRs with new examples welcome — especially for patterns not yet covered (sequential-pipeline, routing, parallelization-voting, evaluator-optimizer) or ecosystems that include a **custom MCP** scaffold. See the top-level `README.md` for the roadmap.
