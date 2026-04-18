# Project-mode template

This template is identical in content to `plugin-template/` but targets the in-project `.claude/` tree instead of a standalone plugin directory.

The scaffold script maps:

| Plugin mode | Project mode |
|---|---|
| `.claude-plugin/plugin.json` | (not written — projects don't need a manifest) |
| `commands/*.md` | `.claude/commands/*.md` |
| `agents/*.md` | `.claude/agents/*.md` |
| `skills/*/SKILL.md` | `.claude/skills/*/SKILL.md` |
| `hooks/hooks.json` | `.claude/settings.json` (hooks key merged into existing settings) |
| `.mcp.json` | `.mcp.json` (repo root, merged with existing) |
| `mcps/<name>/` | `mcps/<name>/` (repo root sibling of `.claude/`) |

The scaffold script reuses the same `.tpl` files from `plugin-template/` — we don't duplicate them here.
