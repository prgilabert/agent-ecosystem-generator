# Frontmatter patterns — how to write descriptions that actually trigger

Descriptions are the **primary triggering mechanism**. A correct description fires the primitive when the user needs it; a generic one sits idle. Claude tends to *under-trigger*, so descriptions must be actively "pushy".

## Hard rules (validator enforces)

1. **Third person**. Never "I ..." or "You ...". Write about the primitive as an external tool.
   - ✗ "I review PRs for security"
   - ✗ "You can use this to review PRs"
   - ✓ "Reviews pull requests for security vulnerabilities ..."

2. **Explicit trigger cue**. Include at least one of:
   - "Use when ..."
   - "Use PROACTIVELY ..."
   - "Use immediately after ..."
   - "Use whenever ..."

3. **Length**. 150–1024 characters. Below 150 → too generic. Above 1024 → the model ignores the tail.

4. **Keyword density**. Include literal words the end user would type (tool names, file extensions, exact phrases). Front-load them.

## Structure template

```
<What it does — one sentence, verb-first, third person, specific output>.
Use <trigger cue> the user <situation-keyword>, or when <observable signal>.
<Optional: one disambiguation sentence — what this is NOT for>.
```

**Example (agent)**:
```
Reviews pull request diffs for security vulnerabilities (SQL injection, XSS,
leaked secrets, insecure auth flows). Use PROACTIVELY whenever a diff is
visible or the user asks to "check security", "audit this PR", or "security
review". Does not cover performance or test coverage — those are separate
agents.
```

**Example (skill)**:
```
Generates Conventional Commits messages from staged git diffs. Use when the
user says "commit", "write a commit message", or "ship this", or immediately
after running `git add`. Outputs a single-line subject plus a wrapped body
with breaking-change footer when applicable.
```

## Anti-patterns

- **Generic verbs**: "helps", "manages", "handles". Replace with the specific action.
- **Implementation leakage**: "uses LLM to..." — the end user does not care.
- **Pronouns that rotate POV**: mixing "this" and "you" confuses the router.
- **No disambiguation**: if two primitives overlap semantically, add a "does NOT cover X" line to each.

## Keywords to front-load

Pick keywords the end user will type verbatim. Examples by domain:

| Domain | Front-load |
|---|---|
| PR review | "diff", "PR", "pull request", "review", "ship" |
| Data pipeline | "pipeline", "ingestion", "ETL", "run", "backfill" |
| Customer support | "ticket", "case", "customer", "reply", "triage" |
| Infra / deploy | "deploy", "rollback", "canary", "alert", "SLO" |

## Disambiguation when primitives overlap

If two agents both touch "security", differentiate by **scope**:

- `dep-auditor` — "Audits third-party dependency versions against CVE database. Use when user says 'check deps', 'audit packages', 'CVE scan'. Does NOT review application code."
- `code-auditor` — "Reviews application source for security anti-patterns (SQLi, XSS, auth). Use PROACTIVELY on diffs. Does NOT audit dependencies."

The validator's `overlap-tokens` rule fails when pairwise Jaccard >0.6 — disambiguation sentences drop Jaccard naturally.

## Checklist before committing a description

- [ ] Third-person, verb-first first sentence
- [ ] ≥1 explicit trigger cue ("Use when / Use PROACTIVELY / Use whenever")
- [ ] ≥3 literal keywords the user would type
- [ ] 150 ≤ length ≤ 1024
- [ ] If this primitive has semantic neighbours, includes a "does NOT" line
