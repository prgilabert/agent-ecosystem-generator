"""PostToolUse hook: if the written file is a primitive inside an ecosystem the
generator produced, run validate_ecosystem.py --quick against its output dir.

The hook reads the tool input from stdin (Claude Code convention) and does a
soft best-effort validation. It never blocks — it only emits warnings to
stderr so Claude can self-correct.

Skip silently if:
- the path is outside an obvious ecosystem output (no `.claude-plugin/` or
  `.claude/` ancestor with our scaffold markers),
- the file has no frontmatter,
- pyyaml is missing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    file_path = (
        payload.get("tool_input", {}).get("file_path")
        or payload.get("tool_input", {}).get("path")
    )
    if not file_path:
        sys.exit(0)

    p = Path(file_path)
    if p.suffix.lower() != ".md":
        sys.exit(0)

    root = _find_ecosystem_root(p)
    if root is None:
        sys.exit(0)

    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not plugin_root:
        sys.exit(0)
    validator = Path(plugin_root) / "skills" / "ecosystem-generator" / "scripts" / "validate_ecosystem.py"
    if not validator.exists():
        sys.exit(0)

    try:
        res = subprocess.run(
            ["python", str(validator), "--target", str(root), "--quick"],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except Exception as exc:
        print(f"[ecosystem-generator] quick-validate skipped: {exc}", file=sys.stderr)
        sys.exit(0)

    if res.returncode != 0:
        sys.exit(0)

    try:
        out = json.loads(res.stdout)
    except Exception:
        sys.exit(0)

    fails = [r for r in out.get("rules", []) if r.get("severity") == "error" and not r.get("passed")]
    if fails:
        print(f"[ecosystem-generator] quick-validate flagged {len(fails)} issue(s) in {root}:", file=sys.stderr)
        for f in fails[:5]:
            print(f"  - {f['id']}: {f.get('details','')} ({f.get('primitive','')})", file=sys.stderr)


def _find_ecosystem_root(p: Path) -> Path | None:
    for parent in [p, *p.parents]:
        if (parent / ".claude-plugin" / "plugin.json").exists():
            return parent
        if (parent / ".claude").is_dir() and any(
            (parent / ".claude" / sub).exists() for sub in ("commands", "agents", "skills")
        ):
            return parent
    return None


if __name__ == "__main__":
    main()
