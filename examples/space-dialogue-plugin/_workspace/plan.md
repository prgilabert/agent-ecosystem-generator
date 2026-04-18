# Ecosystem Plan: space-dialogue-plugin

**Pattern**: orchestrator-workers
**Rationale**: spec.json sub-tasks decompose into 4 independent-enough workers — plot-writer runs first to generate a shared outline, then astronaut-voice and robot-voice run in parallel (both consume only the plot outline), and finally dialogue-reviewer assembles and saves; the parallel character agents justify orchestrator-workers over a flat sequential pipeline.

```plan
name: space-dialogue-plugin
description: >
  Generates short dramatic-comedy dialogue stories between a fixed astronaut and
  a robot assistant from a user prompt, saved as a Markdown file. Use when the
  user invokes /escribe-dialogo or asks to write a space dialogue, relato, or
  historia with two characters.
pattern: orchestrator-workers
orchestrator:
  kind: command
  name: escribe-dialogo
  entry_file: commands/escribe-dialogo.md
agents:
  - name: plot-writer
    role: Generates a structured story outline (scene beats, emotional arc, dramatic-comedy moments) from the user prompt before any character dialogue is written.
    tools: [Read]
    model: sonnet
    description: >
      Generates a structured dramatic-comedy story outline — scene beats, emotional
      arc, and key comedic/dramatic moments — from a short user-provided space
      scenario prompt. Use PROACTIVELY as the first step when /escribe-dialogo is
      invoked or the user asks to write a space story, dialogo, or relato. Outputs
      a plain-text outline that astronaut-voice and robot-voice agents will consume.
      Does not write any dialogue lines — only the plot structure.
  - name: astronaut-voice
    role: Writes all dialogue lines for the astronaut character, grounded in the plot outline produced by plot-writer.
    tools: [Read]
    model: sonnet
    description: >
      Writes all dialogue lines for the astronaut character in a dramatic-comedy
      short story, grounded in the plot outline provided by plot-writer. Use
      PROACTIVELY in parallel with robot-voice, immediately after plot-writer
      completes. Outputs a numbered list of astronaut lines keyed to outline beats.
      Does not write robot lines, does not format the final story, and does not
      save any file.
  - name: robot-voice
    role: Writes all dialogue lines for the robot assistant character, grounded in the plot outline produced by plot-writer.
    tools: [Read]
    model: haiku
    description: >
      Writes all dialogue lines for the robot assistant character in a
      dramatic-comedy short story, grounded in the plot outline provided by
      plot-writer. Use PROACTIVELY in parallel with astronaut-voice, immediately
      after plot-writer completes. Outputs a numbered list of robot lines keyed
      to outline beats. Does not write astronaut lines, does not format the final
      story, and does not save any file.
  - name: dialogue-reviewer
    role: Interleaves astronaut and robot lines into a cohesive dramatic-comedy dialogue, applies tone polish, formats as Markdown, and saves the .md file.
    tools: [Read, Write, Bash]
    model: sonnet
    description: >
      Interleaves astronaut-voice and robot-voice output into a cohesive
      dramatic-comedy dialogue, applies tone polish, formats the result as a
      well-structured Markdown document with title and labeled character turns,
      and saves it as dialogue-<slug>-<timestamp>.md in the current working
      directory. Use PROACTIVELY as the final step after both astronaut-voice and
      robot-voice complete. Does not generate new plot content — only assembles,
      polishes, and saves. Warns before overwriting an existing file.
skills: []
mcps: []
hooks: []
```
