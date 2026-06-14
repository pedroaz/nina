---
name: tool-log
description: Track and reuse known-good shell commands and tool workflows in this repository. Use when a task in this repo is about finding or reusing working commands, avoiding trial-and-error tool selection, or recording a newly successful command so future Codex sessions can start from a proven path.
---

# Tool Log

## Purpose

Use this skill to avoid re-discovering working commands in this repository.

## Workflow

1. Read `references/known-good-tools.md` before choosing shell commands.
2. Prefer the narrowest command already known to work here.
3. If a command succeeds and is reusable, add it to `references/known-good-tools.md` immediately.
4. Log the exact command, what it did, and any constraint such as sandboxing or escalation.
5. Do not brute-force multiple unrelated tools when one known-good path already exists.

## Updating The Log

- Add a new entry when a command is reusable for future repo work.
- Keep entries short and exact.
- Prefer command forms that worked in this environment over generic advice.
- If a command failed, record it only when the failure changes future choice.

## Current Log

See `references/known-good-tools.md` for the live list of working commands.
