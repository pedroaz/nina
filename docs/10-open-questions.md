# Open Questions

These do not block the full plan, but they should be resolved before the relevant implementation phase.

## OpenTUI Details

- What exact OpenTUI package or repository should `apps/tui` use?
- Does it require TypeScript or JavaScript, or does it have a Python binding?
- How should the TUI be launched from `nina tui`?

Default decision until validated:

- Keep all business logic in Python.
- Allow `apps/tui` to use the runtime required by OpenTUI.
- Launch it as a client process that talks to the local daemon API.

## OpenAI And Codex Auth

Resolved:

- Nina uses the Codex auth file as the default subscription-backed path for chat and agent calls.
- The explicit `openai` provider and research mode stay API-key-only.
- Do not treat a Codex/ChatGPT login as a substitute for `OPENAI_API_KEY`.

## Delete Semantics

The user said deleted items should be deleted from Obsidian.

Recommended behavior:

- Move linked notes to `System/Deleted/`.
- Hide them from active Nina views.
- Add hard delete later.

Reason:

- This protects the personal vault from accidental data loss while still making delete behave correctly in the app.

## Task Fields

Nina uses simple tasks only.

Deferred fields:

- priority.
- due date.
- labels.
- estimates.
- dependencies.
- recurrence.

## Profile System

Nina only supports one profile.

Deferred questions:

- How to move the same setup between personal and work computers?
- Whether config should support export/import.
- Whether work/personal should become named profiles later.

## Obsidian Opening

Need to validate the best Linux command for opening a vault file in Obsidian.

Possible approaches:

- Obsidian URI scheme.
- configured shell command.
- print file path as fallback.
