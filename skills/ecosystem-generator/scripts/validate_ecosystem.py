"""Structural + semantic validation of a generated ecosystem.

Produces validation.json with one entry per rule. See references/schemas.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import re

from utils import (
    FIRST_PERSON,
    Frontmatter,
    has_trigger_cue,
    iter_primitive_files,
    jaccard,
    load_md_with_frontmatter,
    tokens,
)


# ---------------------------------------------------------------------------
# Rule results
# ---------------------------------------------------------------------------

@dataclass
class RuleResult:
    id: str
    severity: str  # "error" | "warning" | "info"
    passed: bool
    details: str = ""
    primitive: str = ""


@dataclass
class FixHint:
    rule: str
    primitive: str
    suggestion: str


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def rule_schema_parse(files: list[Path]) -> tuple[list[RuleResult], list[Frontmatter]]:
    results: list[RuleResult] = []
    parsed: list[Frontmatter] = []
    for f in files:
        fm = load_md_with_frontmatter(f)
        if fm is None:
            results.append(RuleResult(
                id="schema-parse",
                severity="error",
                passed=False,
                details=f"no YAML frontmatter found",
                primitive=str(f),
            ))
            continue
        meta = fm.meta or {}
        required = _required_fields_for(f)
        missing = [k for k in required if not meta.get(k)]
        if missing:
            results.append(RuleResult(
                id="schema-parse",
                severity="error",
                passed=False,
                details=f"missing required fields: {missing}",
                primitive=str(f),
            ))
        else:
            results.append(RuleResult(id="schema-parse", severity="error", passed=True, primitive=str(f)))
            parsed.append(fm)
    return results, parsed


def _required_fields_for(path: Path) -> list[str]:
    parts = {p.lower() for p in path.parts}
    if "commands" in parts:
        return ["description"]
    if "agents" in parts:
        return ["name", "description"]
    if "skills" in parts:
        return ["name", "description"]
    return ["description"]


_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


def rule_pushy_ness(parsed: list[Frontmatter], files_by_fm: dict[int, Path]) -> list[RuleResult]:
    results: list[RuleResult] = []
    for fm in parsed:
        desc = (fm.meta.get("description") or "").strip()
        primitive = str(files_by_fm.get(id(fm), "unknown"))
        issues: list[str] = []
        if len(desc) < 150:
            issues.append(f"too short ({len(desc)} < 150 chars)")
        if len(desc) > 1024:
            issues.append(f"too long ({len(desc)} > 1024 chars)")
        if not has_trigger_cue(desc):
            issues.append("missing explicit trigger cue ('Use when', 'Use PROACTIVELY', 'Use whenever')")
        # Quoted user phrases may legitimately contain first-person words — strip them first.
        unquoted = _QUOTED.sub("", desc)
        if FIRST_PERSON.search(unquoted):
            issues.append("uses first/second-person pronouns outside quoted user phrases (must be third-person)")
        if issues:
            results.append(RuleResult(
                id="pushy-ness",
                severity="error",
                passed=False,
                details="; ".join(issues),
                primitive=primitive,
            ))
        else:
            results.append(RuleResult(id="pushy-ness", severity="error", passed=True, primitive=primitive))
    return results


def rule_overlap(parsed: list[Frontmatter], files_by_fm: dict[int, Path]) -> list[RuleResult]:
    agents = [fm for fm in parsed if "agents" in {p.lower() for p in files_by_fm[id(fm)].parts}]
    results: list[RuleResult] = []
    for i, a in enumerate(agents):
        for b in agents[i + 1:]:
            j = jaccard(a.meta.get("description", ""), b.meta.get("description", ""))
            if j > 0.6:
                results.append(RuleResult(
                    id="overlap-tokens",
                    severity="error",
                    passed=False,
                    details=f"Jaccard={j:.2f} > 0.6 between {files_by_fm[id(a)].name} and {files_by_fm[id(b)].name}",
                    primitive=str(files_by_fm[id(b)]),
                ))
    if not results:
        results.append(RuleResult(id="overlap-tokens", severity="error", passed=True))
    return results


def rule_coverage(spec: dict | None, files: list[Path]) -> list[RuleResult]:
    """Every spec.json sub_task must be covered by ≥1 primitive.

    Coverage is measured by token-overlap between the sub_task (id + description)
    and each primitive's (filename + description + body), using Jaccard ≥ 0.15 as
    the 'clearly related' threshold. This tolerates renames like
    'security-check' → agent 'security-reviewer'.
    """
    if not spec or "sub_tasks" not in spec:
        return [RuleResult(id="coverage", severity="warning", passed=True, details="no spec.json")]

    primitive_signatures: list[tuple[Path, set[str]]] = []
    for f in files:
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        primitive_signatures.append((f, tokens(f.name + " " + txt)))

    missing: list[str] = []
    for t in spec["sub_tasks"]:
        task_tokens = tokens(t["id"].replace("-", " ") + " " + t.get("description", ""))
        if not task_tokens:
            continue
        best = 0.0
        for _, sig in primitive_signatures:
            if not sig:
                continue
            score = len(task_tokens & sig) / len(task_tokens | sig)
            if score > best:
                best = score
        if best < 0.15:
            missing.append(t["id"])

    if missing:
        return [RuleResult(
            id="coverage",
            severity="warning",
            passed=False,
            details=f"sub_tasks with weak coverage (Jaccard<0.15): {missing}",
        )]
    return [RuleResult(id="coverage", severity="warning", passed=True)]


def rule_orchestrator_workers(target: Path, plan: dict | None) -> list[RuleResult]:
    if not plan:
        return [RuleResult(id="orchestrator-references-workers", severity="error", passed=True, details="no plan.md")]
    orch_name = plan["orchestrator"]["name"]
    candidates = list(target.rglob(f"{orch_name}.md"))
    if not candidates:
        return [RuleResult(
            id="orchestrator-references-workers",
            severity="error",
            passed=False,
            details=f"orchestrator command {orch_name}.md not found in target",
        )]
    body = candidates[0].read_text(encoding="utf-8")
    missing = [a["name"] for a in plan.get("agents", []) if a["name"] not in body]
    if missing:
        return [RuleResult(
            id="orchestrator-references-workers",
            severity="error",
            passed=False,
            details=f"orchestrator {orch_name}.md does not mention: {missing}",
            primitive=str(candidates[0]),
        )]
    return [RuleResult(id="orchestrator-references-workers", severity="error", passed=True)]


def rule_mcp_wiring(target: Path, plan: dict | None) -> list[RuleResult]:
    mcp_json = _find_mcp_json(target)
    if plan and not plan.get("mcps"):
        return [RuleResult(id="mcp-wiring", severity="error", passed=True, details="no MCPs in plan")]
    if not mcp_json:
        if plan and plan.get("mcps"):
            return [RuleResult(
                id="mcp-wiring",
                severity="error",
                passed=False,
                details="plan has MCPs but .mcp.json is missing",
            )]
        return [RuleResult(id="mcp-wiring", severity="error", passed=True)]

    cfg = json.loads(mcp_json.read_text(encoding="utf-8"))
    servers = cfg.get("mcpServers", {})
    errs: list[str] = []
    for mcp in (plan or {}).get("mcps", []):
        if mcp["name"] not in servers:
            errs.append(f"{mcp['name']} declared in plan but missing from .mcp.json")
        elif mcp["mode"] == "custom":
            # check that the path in args exists somewhere reasonable
            entry = servers[mcp["name"]]
            path_hints = [a for a in entry.get("args", []) if isinstance(a, str) and (a.endswith(".py") or a.endswith(".ts"))]
            if not path_hints:
                errs.append(f"{mcp['name']} has no script path in its args")
    if errs:
        return [RuleResult(id="mcp-wiring", severity="error", passed=False, details="; ".join(errs))]
    return [RuleResult(id="mcp-wiring", severity="error", passed=True)]


def _find_mcp_json(target: Path) -> Path | None:
    direct = target / ".mcp.json"
    if direct.exists():
        return direct
    claude_dir = target / ".claude" / ".mcp.json"
    if claude_dir.exists():
        return claude_dir
    return None


def rule_tool_allowlist(parsed: list[Frontmatter], files_by_fm: dict[int, Path]) -> list[RuleResult]:
    results: list[RuleResult] = []
    for fm in parsed:
        p = files_by_fm.get(id(fm))
        if p is None or "agents" not in {x.lower() for x in p.parts}:
            continue
        tools = fm.meta.get("tools", [])
        if isinstance(tools, str):
            tools = [t.strip() for t in tools.split(",")]
        pm = fm.meta.get("permissionMode")
        if pm == "bypassPermissions":
            results.append(RuleResult(
                id="tool-allowlist-sane",
                severity="error",
                passed=False,
                details="permissionMode: bypassPermissions is forbidden",
                primitive=str(p),
            ))
            continue
        if any("bash" in str(t).lower() for t in tools):
            search_space = (fm.body + " " + fm.meta.get("description", "")).lower()
            justification_phrases = [
                "bash is needed because",
                "bash because",
                "needs bash",
                "requires bash",
                "uses bash to",
                "needs shell",
                "runs shell",
                "runs `",  # agent narrates a shell command in body
            ]
            if not any(k in search_space for k in justification_phrases):
                results.append(RuleResult(
                    id="tool-allowlist-sane",
                    severity="error",
                    passed=False,
                    details="agent grants Bash but no justification phrase found in description or body",
                    primitive=str(p),
                ))
                continue
        results.append(RuleResult(id="tool-allowlist-sane", severity="error", passed=True, primitive=str(p)))
    if not results:
        results.append(RuleResult(id="tool-allowlist-sane", severity="error", passed=True))
    return results


def rule_skill_sections(files: list[Path]) -> list[RuleResult]:
    sections = ["purpose", "when to use", "workflow", "inputs", "outputs", "examples"]
    results: list[RuleResult] = []
    for f in files:
        parts = {p.lower() for p in f.parts}
        if "skills" not in parts or f.name.upper() != "SKILL.MD":
            continue
        text = f.read_text(encoding="utf-8").lower()
        missing = [s for s in sections if f"## {s}" not in text]
        if missing:
            results.append(RuleResult(
                id="skill-section-completeness",
                severity="warning",
                passed=False,
                details=f"missing sections: {missing}",
                primitive=str(f),
            ))
        else:
            results.append(RuleResult(id="skill-section-completeness", severity="warning", passed=True, primitive=str(f)))
    if not results:
        results.append(RuleResult(id="skill-section-completeness", severity="warning", passed=True))
    return results


# ---------------------------------------------------------------------------
# Fix hint generation
# ---------------------------------------------------------------------------

def build_fix_hints(rules: list[RuleResult]) -> list[FixHint]:
    hints: list[FixHint] = []
    for r in rules:
        if r.passed or r.severity != "error":
            continue
        hints.append(FixHint(
            rule=r.id,
            primitive=r.primitive,
            suggestion=_suggestion_for(r),
        ))
    return hints


def _suggestion_for(r: RuleResult) -> str:
    if r.id == "pushy-ness":
        return (
            "Rewrite the description to be third-person, include an explicit trigger cue "
            "('Use when...', 'Use PROACTIVELY'), and land between 150–1024 chars. "
            "See references/frontmatter-patterns.md."
        )
    if r.id == "overlap-tokens":
        return (
            "Two agent descriptions overlap too much. Disambiguate by narrowing scope and "
            "adding a 'Does NOT cover X' sentence to each."
        )
    if r.id == "schema-parse":
        return "Add the missing required frontmatter fields at the top of the file."
    if r.id == "orchestrator-references-workers":
        return (
            "Edit the orchestrator command body to mention each worker agent by name, ideally "
            "as `Spawn sub-agent <name>` under the appropriate phase."
        )
    if r.id == "mcp-wiring":
        return (
            "Ensure every plan.mcps[] entry appears in .mcp.json with a stdio command that "
            "resolves to the scaffolded server path or the referenced package."
        )
    if r.id == "tool-allowlist-sane":
        return (
            "Remove permissionMode: bypassPermissions. If Bash is granted, add a short "
            "justification sentence in the agent body (e.g. 'Bash is needed because...')."
        )
    return "Review the details and adjust the primitive accordingly."


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, help="generated ecosystem output path")
    ap.add_argument("--workspace", default=None, help="workspace dir (to read spec.json + plan.md)")
    ap.add_argument("--quick", action="store_true", help="only schema + pushy")
    ap.add_argument("--full", action="store_true", help="run all rules (default)")
    args = ap.parse_args()

    target = Path(args.target).resolve()
    workspace = Path(args.workspace).resolve() if args.workspace else None

    spec = _load_json(workspace / "spec.json") if workspace else None
    plan = _load_plan(workspace) if workspace else None

    files = iter_primitive_files(target)
    all_rules: list[RuleResult] = []

    schema_results, parsed = rule_schema_parse(files)
    all_rules.extend(schema_results)
    files_by_fm = {id(fm): _path_for(fm, files) for fm in parsed}

    all_rules.extend(rule_pushy_ness(parsed, files_by_fm))

    if not args.quick:
        all_rules.extend(rule_overlap(parsed, files_by_fm))
        all_rules.extend(rule_coverage(spec, files))
        all_rules.extend(rule_orchestrator_workers(target, plan))
        all_rules.extend(rule_mcp_wiring(target, plan))
        all_rules.extend(rule_tool_allowlist(parsed, files_by_fm))
        all_rules.extend(rule_skill_sections(files))

    errors_failed = [r for r in all_rules if r.severity == "error" and not r.passed]
    status = "fail" if errors_failed else "pass"
    passed_count = sum(1 for r in all_rules if r.passed)
    score = round(passed_count / len(all_rules), 2) if all_rules else 1.0

    iteration = _iteration_from_workspace(workspace)
    out = {
        "status": status,
        "score": score,
        "iteration": iteration,
        "rules": [asdict(r) for r in all_rules],
        "fix_hints": [asdict(h) for h in build_fix_hints(all_rules)] if status == "fail" else [],
    }

    if workspace:
        (workspace / "validation.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


def _path_for(fm: Frontmatter, files: list[Path]) -> Path:
    # Re-parse each file's raw once; map identity via body content equality.
    for f in files:
        try:
            if f.read_text(encoding="utf-8") == fm.raw:
                return f
        except OSError:
            continue
    return Path("unknown")


def _load_json(p: Path) -> dict | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_plan(workspace: Path) -> dict | None:
    plan_path = workspace / "plan.md"
    if not plan_path.exists():
        return None
    try:
        from utils import parse_plan

        return parse_plan(plan_path)
    except Exception:
        return None


def _iteration_from_workspace(workspace: Path | None) -> int:
    if workspace is None:
        return 1
    log = workspace / "build-log.json"
    if not log.exists():
        return 1
    try:
        return int(json.loads(log.read_text(encoding="utf-8")).get("iteration", 1))
    except Exception:
        return 1


if __name__ == "__main__":
    main()
