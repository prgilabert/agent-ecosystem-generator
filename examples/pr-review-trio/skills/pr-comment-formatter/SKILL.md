---
name: pr-comment-formatter
description: "Formats aggregated reviewer findings into a single structured PR comment with collapsed sections per checker, severity icons, and a top summary. Use when aggregating security, performance, or test findings for a PR, or when the orchestrator assembles a final report. Does NOT fetch diffs or call the GitHub API — that is the orchestrator's job."
---

# Pr Comment Formatter

## Purpose

Turn a list of findings into a reviewer-friendly markdown comment.

## When to use

After all three checkers return. Before the orchestrator posts a comment.

## Workflow

1. Group findings by checker.
2. Sort by severity.
3. Render markdown with `<details>` sections per checker.


## Inputs

Array of findings objects.

## Outputs

Markdown string ready to paste as a PR comment.

## Examples

See assets/examples/.
