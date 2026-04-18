# Orchestration patterns — pick one, justify

Five canonical patterns from Anthropic's *Building effective agents* (Schluntz & Zhang, Dec 2024). The orchestrator picks one during Phase 2 and records rationale in `plan.md`.

## 1. Orchestrator–workers

**When**: N sub-tasks are knowable but independent; breadth-first exploration; output aggregation at the end.

**Shape**: orchestrator decomposes → spawns N workers in parallel → synthesizes.

**Use for**: PR review (security / performance / tests), multi-source research, parallel codebase exploration.

**Cost**: ~15× tokens vs single-agent. Only justified when output is high-value.

**Pick this if** `spec.json.sub_tasks` are:
- independent of each other,
- roughly equal in effort,
- can run concurrently without shared state.

## 2. Sequential pipeline

**When**: steps have hard dependencies; each step must validate before the next runs.

**Shape**: step 1 → gate → step 2 → gate → step 3.

**Use for**: data pipeline (fetch → classify → notify), deployment (build → test → stage → prod).

**Pick this if** `spec.json.sub_tasks` are:
- ordered and dependent,
- each step's output feeds the next,
- a failure early should halt the pipeline.

## 3. Routing

**When**: one of several specialists should handle the input; the choice is made up-front by a classifier.

**Shape**: classifier → specialist A | B | C.

**Use for**: customer support triage, multi-language code reviewers, cost-tier routing (Haiku for simple, Opus for hard).

**Pick this if** `spec.json.sub_tasks` are:
- mutually exclusive (exactly one should handle),
- classifiable from the input alone.

## 4. Parallelization-voting

**When**: a high-stakes decision benefits from multiple independent opinions aggregated.

**Shape**: N independent evaluators → aggregator (majority / best-of-N / evaluator LLM).

**Use for**: security review where false negatives are unacceptable, moderation, code-merge sign-off.

**Pick this if**:
- cost of a false negative is high,
- variance across evaluators is expected to carry signal.

## 5. Evaluator-optimizer

**When**: generator-critic loop with clear rubric; iterate until criteria met.

**Shape**: generator → evaluator (rubric) → feedback → generator … → done.

**Use for**: copy writing with style rubric, code generation with test gate, prompt optimization (this is exactly what skill-creator does for descriptions).

**Pick this if**:
- you can state a rubric the evaluator can apply consistently,
- the LLM can articulate actionable feedback to the generator.

**Anti-pattern**: using this when the rubric is ambiguous — it burns tokens without convergence.

## Primitive choice per pattern

Orchestration pattern ≠ primitive list. After picking a pattern, decide each sub-task's primitive:

| Sub-task property | Primitive |
|---|---|
| Verbose, disposable output (logs, research) | **Sub-agent** (isolated ctx) |
| Auto-triggering, semantic, short body | **Skill** |
| Manual slash shortcut, deterministic prompt | **Slash command** |
| Must always run, enforcement | **Hook** (deterministic) |
| External data read/write | **MCP** (referenced or custom) |
| Rule Claude should always know | **CLAUDE.md** snippet |

**Rule of thumb**: start with the minimum number of sub-agents. Each sub-agent adds context-isolation overhead; skills + hooks compose better if the sub-task doesn't generate verbose output.

## Decision table: "do I need a sub-agent here?"

| Condition | Sub-agent | Skill | Hook |
|---|---|---|---|
| Output is >2k tokens of research/logs | ✅ | | |
| Needs tool restrictions (e.g. Read-only) | ✅ | | |
| Should run in parallel with other work | ✅ | | |
| Semantic auto-trigger from user phrasing | | ✅ | |
| Must run every time event X fires | | | ✅ |
| Deterministic (no LLM judgment needed) | | | ✅ |

## Justification sentence (required in `plan.md`)

Every `plan.md` must start with one sentence like:

> **Pattern**: orchestrator-workers. **Rationale**: `spec.json` lists 3 independent checkers (security/performance/tests) that can run in parallel and whose outputs aggregate into a single PR-review comment.

The validator's `pattern-fit-judgment` rule reads this sentence.
