"""Trigger firerate eval.

Adapts skill-creator's trigger evals to the ecosystem case: for every primitive
(agent, skill, command), generate N probe prompts from the trigger phrases in
its description and check that the intended primitive "wins" the routing.

Design choice: this script does NOT call the Anthropic API itself. It computes
a token-overlap-based proxy score between each probe and every primitive
description, then marks the probe as "fired correctly" if the intended
primitive has the top score. This is a cheap, deterministic, offline proxy
that correlates with real-model routing enough to catch the common failure
modes (generic descriptions, overlap, missing keywords). A future v2 can swap
the proxy for a real model call.

Outputs: merges a `trigger-eval-firerate` rule per primitive into
validation.json (creating it if absent).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import iter_primitive_files, load_md_with_frontmatter, tokens

TRIGGER_PHRASE_RE = re.compile(r"use\s+(?:when|whenever|proactively|immediately\s+after)\s+([^.]+)", re.IGNORECASE)
KEYWORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9-]+")


def extract_probes(description: str, samples: int) -> list[str]:
    """Generate N probe prompts from the description's trigger clauses + keywords."""
    probes: list[str] = []

    # Trigger phrases: "Use when X", "Use whenever Y".
    for m in TRIGGER_PHRASE_RE.finditer(description):
        phrase = m.group(1).strip().rstrip(",.")
        # convert clause to a first-person user query
        probes.append(_as_user_query(phrase))

    # Keyword bigrams from the first sentence (often the most trigger-like words).
    first_sentence = description.split(".", 1)[0]
    keywords = [w.lower() for w in KEYWORD_RE.findall(first_sentence) if len(w) > 3]
    stopwords = {"use", "when", "whenever", "proactively", "immediately", "after", "with", "this", "that", "does", "not", "cover"}
    keywords = [k for k in keywords if k not in stopwords]
    for i in range(min(samples, len(keywords))):
        probes.append(f"I need help with {keywords[i]} right now")

    # Literal quoted phrases inside the description
    for m in re.finditer(r'"([^"]{3,40})"', description):
        probes.append(m.group(1))

    # Deduplicate + truncate
    unique: list[str] = []
    seen = set()
    for p in probes:
        low = p.lower().strip()
        if low and low not in seen:
            seen.add(low)
            unique.append(p)
        if len(unique) >= samples:
            break
    while len(unique) < samples and keywords:
        unique.append(f"can you help me {keywords[len(unique) % len(keywords)]}")
    return unique[:samples]


def _as_user_query(phrase: str) -> str:
    phrase = phrase.strip()
    if phrase.startswith("the user"):
        phrase = phrase[len("the user"):].strip()
    if phrase.startswith("user"):
        phrase = phrase[len("user"):].strip()
    return phrase.strip('"\' ').capitalize() or "please help"


def score(probe: str, description: str) -> float:
    tp = tokens(probe)
    td = tokens(description)
    if not tp or not td:
        return 0.0
    return len(tp & td) / max(len(tp), 1)


def _primitive_kind(path: Path) -> str:
    parts = {p.lower() for p in path.parts}
    if "agents" in parts:
        return "agent"
    if "skills" in parts:
        return "skill"
    if "commands" in parts:
        return "command"
    return "other"


def evaluate(target: Path, samples: int = 10) -> dict[str, Any]:
    """Eval trigger firerate for auto-selected primitives only (skills, commands).

    Sub-agents are *called by name* from orchestrators via the Agent tool; they
    do not compete for routing based on their description, so running this eval
    on them would produce noise. Skills and top-level commands DO compete for
    user-intent routing and are the right scope.
    """
    files = iter_primitive_files(target)
    all_prims: list[dict] = []
    for f in files:
        fm = load_md_with_frontmatter(f)
        if fm is None:
            continue
        desc = fm.meta.get("description", "").strip()
        if not desc:
            continue
        all_prims.append({
            "path": str(f),
            "name": fm.meta.get("name", f.stem),
            "description": desc,
            "kind": _primitive_kind(f),
        })

    # Competitors: skills + commands. Agents are skipped.
    competitors = [p for p in all_prims if p["kind"] in ("skill", "command")]

    results: list[dict] = []
    for prim in competitors:
        probes = extract_probes(prim["description"], samples)
        hits = 0
        for probe in probes:
            scores = [(p["name"], score(probe, p["description"])) for p in competitors]
            scores.sort(key=lambda t: t[1], reverse=True)
            winner = scores[0][0] if scores else None
            if winner == prim["name"]:
                hits += 1
        firerate = hits / max(len(probes), 1)
        results.append({
            "primitive": prim["path"],
            "name": prim["name"],
            "kind": prim["kind"],
            "probes": len(probes),
            "hits": hits,
            "firerate": round(firerate, 2),
            "passed": firerate >= 0.7,
        })
    return {"results": results, "threshold": 0.7, "skipped_agents": sum(1 for p in all_prims if p["kind"] == "agent")}


def merge_into_validation(workspace: Path | None, eval_out: dict) -> None:
    if workspace is None:
        return
    vpath = workspace / "validation.json"
    base = {"status": "pass", "score": 1.0, "iteration": 1, "rules": [], "fix_hints": []}
    if vpath.exists():
        try:
            base = json.loads(vpath.read_text(encoding="utf-8"))
        except Exception:
            pass

    all_pass = True
    new_rules = []
    for r in eval_out["results"]:
        passed = r["passed"]
        if not passed:
            all_pass = False
        new_rules.append({
            "id": "trigger-eval-firerate",
            "severity": "error",
            "passed": passed,
            "details": f"firerate={r['firerate']} (hits {r['hits']}/{r['probes']}, threshold {eval_out['threshold']})",
            "primitive": r["primitive"],
        })
        if not passed:
            base.setdefault("fix_hints", []).append({
                "rule": "trigger-eval-firerate",
                "primitive": r["primitive"],
                "suggestion": (
                    "Firerate below threshold. Make the description more specific: front-load "
                    "literal keywords a user would type, include an explicit 'Use when' cue, and "
                    "add a 'Does NOT cover' disambiguation if it competes with another primitive."
                ),
            })

    base["rules"] = [r for r in base.get("rules", []) if r["id"] != "trigger-eval-firerate"] + new_rules
    if not all_pass:
        base["status"] = "fail"
    # Recompute score.
    total = len(base["rules"])
    passed_count = sum(1 for r in base["rules"] if r["passed"])
    base["score"] = round(passed_count / total, 2) if total else 1.0
    vpath.write_text(json.dumps(base, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--workspace", default=None)
    ap.add_argument("--samples", type=int, default=10)
    args = ap.parse_args()

    target = Path(args.target).resolve()
    workspace = Path(args.workspace).resolve() if args.workspace else None
    out = evaluate(target, samples=args.samples)
    merge_into_validation(workspace, out)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
