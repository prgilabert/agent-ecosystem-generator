"""Shared helpers for the ecosystem-generator scripts."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
ASSETS = PLUGIN_ROOT / "skills" / "ecosystem-generator" / "assets"


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


@dataclass
class Frontmatter:
    meta: dict[str, Any]
    body: str
    raw: str


def parse_frontmatter(text: str) -> Frontmatter | None:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    meta = yaml.safe_load(m.group(1)) or {}
    return Frontmatter(meta=meta, body=m.group(2), raw=text)


def load_md_with_frontmatter(path: Path) -> Frontmatter | None:
    return parse_frontmatter(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# plan.md parsing
# ---------------------------------------------------------------------------

PLAN_BLOCK_RE = re.compile(r"```plan\n(.*?)\n```", re.DOTALL)


def parse_plan(plan_md_path: Path) -> dict[str, Any]:
    text = plan_md_path.read_text(encoding="utf-8")
    m = PLAN_BLOCK_RE.search(text)
    if not m:
        raise ValueError(
            f"plan.md at {plan_md_path} is missing a ```plan ... ``` YAML block"
        )
    plan = yaml.safe_load(m.group(1)) or {}
    _validate_plan_shape(plan, source=plan_md_path)
    return plan


def _validate_plan_shape(plan: dict, source: Path) -> None:
    required_top = ["name", "pattern", "orchestrator"]
    for key in required_top:
        if key not in plan:
            raise ValueError(f"plan.md ({source}) missing required key: {key}")
    plan.setdefault("agents", [])
    plan.setdefault("skills", [])
    plan.setdefault("mcps", [])
    plan.setdefault("hooks", [])


# ---------------------------------------------------------------------------
# Template rendering (dumb string.replace)
# ---------------------------------------------------------------------------

PLACEHOLDER_RE = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}")


def render_template(template_text: str, context: dict[str, Any]) -> str:
    """Replace {{key}} markers with context[key]. Missing keys become empty string."""
    def sub(m: re.Match[str]) -> str:
        key = m.group(1)
        value = context.get(key, "")
        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2)
        return str(value)

    return PLACEHOLDER_RE.sub(sub, template_text)


def render_template_file(template_path: Path, context: dict[str, Any]) -> str:
    return render_template(template_path.read_text(encoding="utf-8"), context)


# ---------------------------------------------------------------------------
# File ops
# ---------------------------------------------------------------------------

def write_file(path: Path, content: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return len(content.encode("utf-8"))


def iter_primitive_files(target: Path) -> list[Path]:
    """Return all .md files that look like primitives (agents, skills, commands)."""
    result: list[Path] = []
    for rel in ["commands", "agents", "skills", ".claude/commands", ".claude/agents", ".claude/skills"]:
        d = target / rel
        if not d.exists():
            continue
        for p in d.rglob("*.md"):
            result.append(p)
    return result


# ---------------------------------------------------------------------------
# Token helpers (pushy-ness, Jaccard)
# ---------------------------------------------------------------------------

TRIGGER_CUES = [
    "use when",
    "use proactively",
    "use immediately after",
    "use whenever",
    "use this when",
    "use this skill when",
    "use this agent when",
]

FIRST_PERSON = re.compile(r"\b(i|me|my|we|our|you|your)\b", re.IGNORECASE)

TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text) if len(t) > 2}


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def has_trigger_cue(description: str) -> bool:
    low = description.lower()
    return any(cue in low for cue in TRIGGER_CUES)


def yaml_quote(s: str) -> str:
    """Wrap a string in YAML-safe double quotes so colons/hashes/newlines can't break the frontmatter."""
    normalized = " ".join(s.split())  # collapse whitespace; frontmatter desc is single-line
    escaped = normalized.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


# ---------------------------------------------------------------------------
# Resolving CLAUDE_PLUGIN_ROOT when running outside Claude Code
# ---------------------------------------------------------------------------

def plugin_root() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return PLUGIN_ROOT
