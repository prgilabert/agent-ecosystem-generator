"""Create a workspace directory for a /generate-ecosystem run."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default=None, help="override workspace name; default is timestamp")
    ap.add_argument(
        "--root",
        default=None,
        help="root under which workspaces are created (default: CLAUDE_PROJECT_DIR or cwd)",
    )
    args = ap.parse_args()

    name = args.name or datetime.now().strftime("%Y%m%d-%H%M%S")
    root_env = args.root or _default_root()
    workspace = Path(root_env) / ".ecosystem-generator" / name
    workspace.mkdir(parents=True, exist_ok=True)

    meta = {
        "workspace_dir": str(workspace),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "iteration": 0,
    }
    (workspace / "workspace.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print(json.dumps(meta, indent=2))


def _default_root() -> str:
    import os

    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


if __name__ == "__main__":
    main()
