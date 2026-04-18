# Examples

Reference ecosystems produced by `agent-ecosystem-generator`. Each subfolder is a **real, installable Claude Code plugin** that came out of the generator — not a hand-written mock.

Browse these before installing the generator yourself to see what `/generate-ecosystem` actually emits.

## Gallery

| Example | Pattern | Primitives | Validation | MCPs | Origin |
|---|---|---|---|---|---|
| [`pr-review-trio/`](./pr-review-trio) | orchestrator-workers | 1 command + 3 sub-agents + 1 skill | pass (0.94) | `github` (referenced) | Synthetic spec (scripts only) |
| [`space-dialogue-plugin/`](./space-dialogue-plugin) | orchestrator-workers (with parallel fan-out) | 1 command + 4 sub-agents | pass (0.95) | none | **Real `/generate-ecosystem` run** |

## Reading an example

Each example folder has two parts:

1. **The generated plugin** (top-level files + `.claude-plugin/`, `agents/`, `commands/`, and `skills/` / `.mcp.json` when applicable). To try any of these yourself inside a Claude Code session:

   ```
   /plugin marketplace add ./examples/<example-name>
   /plugin install <plugin-name>@<marketplace-name>
   ```

   (The marketplace name and plugin name come from each example's `.claude-plugin/plugin.json`.)

2. **`_workspace/`** — the inputs and validator output that produced the plugin. Not part of the installable plugin; kept so you can trace back "what brief → what spec → what plan → what output".
   - `spec.json` — output of the `requirements-interviewer` sub-agent (the structured requirements).
   - `plan.md` — the orchestrator's architecture decision (pattern, agents, skills, MCPs).
   - `validation.json` — the `ecosystem-validator`'s verdict across all rules.

## How these examples were produced

- **`pr-review-trio`** was produced by running the scaffolding scripts directly with a hand-written `spec.json` + `plan.md`, bypassing the full `/generate-ecosystem` interactive flow. Deterministic and reproducible — the output is **byte-identical** to what the full flow would emit for the same plan.
- **`space-dialogue-plugin`** came out of a **real, interactive `/generate-ecosystem` session** — brief in Spanish, interviewer asked clarifying questions, orchestrator picked the pattern, builder materialized files, validator iterated 4 rounds before passing at 0.95. Copied verbatim into `examples/` as-is (with the addition of a hand-written `README.md`).

If you want to regenerate `pr-review-trio` from its `_workspace/` manually:

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
