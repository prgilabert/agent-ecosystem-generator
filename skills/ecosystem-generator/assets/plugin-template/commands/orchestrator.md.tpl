---
description: {{orchestrator_description}}
argument-hint: {{argument_hint}}
allowed-tools: {{allowed_tools}}
---

# /{{orchestrator_name}}

{{orchestrator_body_intro}}

Input: **$ARGUMENTS**

## Pattern: {{pattern}}

{{pattern_rationale}}

## Phases

{{phases_body}}

## Workers

{{workers_body}}

## Error handling

If any worker returns without its expected artifact, surface its final message verbatim and stop. Do not fabricate progress.
