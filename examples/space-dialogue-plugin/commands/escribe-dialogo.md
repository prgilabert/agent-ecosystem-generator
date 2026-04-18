---
description: "Generates short dramatic-comedy dialogue stories between a fixed astronaut and a robot assistant from a user prompt, saved as a Markdown file. Use when the user invokes /escribe-dialogo or asks to write a space dialogue, relato, or historia with two characters."
argument-hint: "<short topic or scenario prompt, e.g. 'una tormenta de meteoros'>"
allowed-tools: Agent, Read, Write, Bash
---

# /escribe-dialogo

Orchestrator for the **space-dialogue-plugin** ecosystem. Given a short topic or scenario prompt, this command produces a fully-formatted dramatic-comedy dialogue between an astronaut and a robot assistant, saved as a Markdown file.

Input: **$ARGUMENTS**

If `$ARGUMENTS` is empty, ask the user for a brief prompt before proceeding.

---

## Pattern: orchestrator-workers

The pipeline runs in three sequential phases. Phases 2a and 2b execute in parallel.

---

## Phase 1 — Plot outline

Spawn the **plot-writer** agent with the user's prompt. Pass the exact text of `$ARGUMENTS` as the scenario.

Using the Agent tool:

> Task for **plot-writer**: "Generate a structured dramatic-comedy plot outline for the following scenario: $ARGUMENTS. Produce numbered scene beats (at least 5), an emotional arc summary (one sentence), and flag 2–3 moments with high comedic or dramatic potential. Output plain text only — no dialogue lines."

Wait for plot-writer to return its outline before proceeding. Store the returned outline as `PLOT_OUTLINE`.

If plot-writer returns without a numbered list of beats, surface its message verbatim and stop.

---

## Phase 2 — Character lines (parallel)

Spawn **astronaut-voice** and **robot-voice** simultaneously using the Agent tool. Pass `PLOT_OUTLINE` to both.

**Task for astronaut-voice:**

> "You have the following plot outline:\n\n<PLOT_OUTLINE>\n\nWrite ALL dialogue lines for the astronaut character — one numbered line per outline beat. Lines must match the dramatic-comedy tone. Do not write any robot lines. Do not format as a story. Return a numbered list only."

**Task for robot-voice:**

> "You have the following plot outline:\n\n<PLOT_OUTLINE>\n\nWrite ALL dialogue lines for the robot assistant character — one numbered line per outline beat. Lines must match the dramatic-comedy tone (the robot is literal-minded and deadpan). Do not write any astronaut lines. Do not format as a story. Return a numbered list only."

Wait for both agents to return. Store results as `ASTRONAUT_LINES` and `ROBOT_LINES`.

If either agent returns without a numbered list, surface its message verbatim and stop.

---

## Phase 3 — Assembly, polish, and save

Spawn the **dialogue-reviewer** agent with all three artifacts.

**Task for dialogue-reviewer:**

> "You have the following inputs:\n\nPLOT OUTLINE:\n<PLOT_OUTLINE>\n\nASTRONAUT LINES:\n<ASTRONAUT_LINES>\n\nROBOT LINES:\n<ROBOT_LINES>\n\nOriginal prompt: $ARGUMENTS\n\nInterleave the lines into a cohesive dramatic-comedy dialogue. Apply tone polish. Format as a Markdown document with:\n- A title derived from the prompt\n- Character turns labeled **Astronauta:** and **Robot:**\n- A brief scene-setting introduction paragraph\n\nDerive a filename slug from the prompt (lowercase, hyphens, max 40 chars) and append a timestamp (YYYYMMDDHHmmss). Save the file as `dialogue-<slug>-<timestamp>.md` in the current working directory. If a file with that name already exists, warn and append `-v2` to the slug before saving.\n\nReturn the absolute path of the saved file and nothing else."

Wait for dialogue-reviewer to return a file path.

---

## Final report

After dialogue-reviewer completes, report to the user:

> "Dialogo guardado en: <returned file path>"

If dialogue-reviewer did not return a file path, surface its full output verbatim and stop.

---

## Error handling

- If any worker returns without its expected artifact, surface its final message verbatim and stop. Do not fabricate progress.
- Do not retry a failed worker automatically. Explain what happened and ask the user whether to retry.
- Never write files yourself — delegate all file I/O to dialogue-reviewer.
