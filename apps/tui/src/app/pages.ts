import type { MainPageFocusTarget, PageName } from "../api/types";

export const PAGE_NAMES: PageName[] = [
  "Tickets",
  "Repositories",
  "Chat",
  "Agent",
  "Research",
  "Meetings",
  "Jobs",
  "Integrations",
  "Config",
];
export const PAGE_DESCRIPTIONS: Record<PageName, string> = {
  Tickets: "Create tasks and review tasks grouped by type",
  Repositories: "Register git repositories used by coding and reviewing tasks",
  Chat: "Ask questions over local Nina context",
  Agent: "Natural language that can auto-run Nina commands",
  Research: "Research a topic and write an Obsidian note",
  Meetings: "Record meetings, transcribe, and summarize",
  Jobs: "Inspect scheduled workflows and recent runs",
  Integrations: "Read-only health for external services (Confluence, Jira, Slack, Teams)",
  Config: "Vault, database, daemon, and runtime settings",
};
export const PAGE_ACCENTS: Record<PageName, string> = {
  Tickets: "#22c55e",
  Repositories: "#38bdf8",
  Chat: "#22d3ee",
  Agent: "#f97316",
  Research: "#eab308",
  Meetings: "#a855f7",
  Jobs: "#60a5fa",
  Integrations: "#14b8a6",
  Config: "#94a3b8",
};
export const PAGE_HELP: Record<PageName, string> = {
  Tickets: "Esc returns to navigation. Tab/Shift+Tab move between pages. F6 toggles focus inside the page. Ctrl+1..Ctrl+9 jump pages. Tasks are always grouped by task_type. Ctrl+Space opens the create-task form. In the form, Ctrl+Up/Down moves between fields, Ctrl+Left/Right changes option fields, Enter creates, and Esc cancels. Ctrl+Up/Down selects a task. Ctrl+E toggles the detail view. Ctrl+G cycles the selected task_type. Ctrl+F cycles the selected task repository. Ctrl+1..Ctrl+8 set task_type directly when a task is selected (1=unclassified, 2=coding, 3=reviewing, 4=research, 5=reminder, 6=blocked, 7=human, 8=done). Ctrl+L opens Codex logs for the selected task. Ctrl+Enter queues classifier/Codex work for the selected task. Ctrl+D deletes a task. Ctrl+A archives a task. PageUp/PageDown scroll the list. Ctrl+R refreshes the page.",
  Repositories: "Esc returns to navigation. Tab/Shift+Tab move between pages. F6 toggles focus inside the page. Ctrl+1..Ctrl+9 jump pages. Type a git repository path, optionally followed by | name, and press Enter to register it. Ctrl+Up/Down moves the selection. PageUp/PageDown scroll the list. Ctrl+R refreshes the page.",
  Chat: "Esc returns to navigation. Tab/Shift+Tab move between pages. F6 toggles focus inside the page. Ctrl+1..Ctrl+9 jump pages. Ctrl+B and Ctrl+F switch between the history and prompt. Enter sends the prompt. Use @path/to/note.md in the prompt to attach a note. While waiting, a loading card shows elapsed time. Use Ctrl+K for page actions/help before clearing chat. Ctrl+. cancels the running response. PageUp/PageDown scroll the history; End jumps to the bottom. Ctrl+R refreshes the page.",
  Agent: "Esc returns to navigation. Tab/Shift+Tab move between pages. F6 toggles focus inside the page. Ctrl+1..Ctrl+9 jump pages. Ctrl+B and Ctrl+F switch between the history and prompt. Enter sends the prompt and may execute tool calls automatically. While waiting, a loading card shows elapsed time. Ctrl+. cancels the running response. PageUp/PageDown scroll the history; End jumps to the bottom.",
  Research: "Esc returns to navigation. Tab/Shift+Tab move between pages. F6 toggles focus inside the page. Ctrl+1..Ctrl+9 jump pages. Ctrl+B and Ctrl+F switch between the history and prompt. Enter runs OpenAI web research and writes a note into Obsidian. While waiting, a loading card shows elapsed time. PageUp/PageDown scroll the report.",
  Meetings: "Esc returns to navigation. Tab/Shift+Tab move between pages. F6 toggles focus inside the page. Ctrl+1..Ctrl+9 jump pages. Up/Down moves the selection. Type a title and press Enter to start a recording. All other actions use Ctrl so the text input does not swallow them: Ctrl+E transcribe + summarize (pipeline), Ctrl+X stop active recording, Ctrl+O open in Obsidian, Ctrl+P play audio, Ctrl+D delete. PageUp/PageDown scroll the list. Ctrl+R refreshes the page.",
  Jobs: "Esc returns to navigation. Tab/Shift+Tab move between pages. F6 toggles focus inside the page. Ctrl+1..Ctrl+9 jump pages. On the Jobs page, Ctrl+Up/Down select a job, Ctrl+A opens that job's runs, Ctrl+E runs it now, Esc (in the runs view) returns to the list, Ctrl+PageUp/PageDown and Home/End scroll. Ctrl+R refreshes the page.",
  Integrations: "Esc returns to navigation. Tab/Shift+Tab move between pages. F6 toggles focus inside the page. Ctrl+1..Ctrl+9 jump pages. Read-only view: each card shows the configured integrations, their last identity ping, latency, and any errors. Run `nina integrations configure <name>` and `nina integrations test <name>` from the CLI to add credentials and re-run a test. Ctrl+R refreshes the page.",
  Config: "Esc returns to navigation. Ctrl+B and Ctrl+F switch between the editable list and the value field. Up and Down change the selected setting. Enter saves the current value. Tab/Shift+Tab move between pages. F6 toggles focus inside the page. Ctrl+1..Ctrl+9 jump pages. Ctrl+R refreshes the page. Ctrl+C quits.",
};
export const PAGE_INTRO: Record<PageName, string> = {
  Tickets: "Tasks start as unclassified and are moved by the AI classifier. Coding and reviewing tasks require a registered repository; reminder and research tasks can stay repository-free.",
  Repositories: "Repositories are git roots that Nina passes to Codex as the working directory for coding and reviewing tasks. Register repo paths here before creating coding or reviewing tasks.",
  Chat: "Chat mode answers questions with LLM-backed Obsidian context via tool calls. Use @path/to/note.md in the prompt to attach a note. It does not run commands or write to the vault.",
  Agent: "Agent mode can plan and execute tool calls (read + write) against the vault, tasks, and jobs. It is intended for natural-language task creation and other safe Nina operations.",
  Research: "Research mode uses OpenAI web search and writes a summary-plus-links note into your Obsidian vault.",
  Meetings: "Meetings are recorded through the daemon-backed CLI or TUI. Each recording creates a Meetings/<date> - <title>.md note in Obsidian. Transcription and summarization are workflows that read the same audio file.",
  Jobs: "Jobs execute Nina workflows on a schedule and keep their run history in SQLite.",
  Integrations: "External services Nina can reach. All interactions are read-only and limited to an identity ping, but the same service layer will power future tasks and jobs.",
  Config: "This view lets you inspect and edit the config file that the daemon and CLI read.",
};
export const PAGE_DEFAULT_FOCUS: Record<PageName, MainPageFocusTarget> = {
  Tickets: "scroll",
  Repositories: "input",
  Chat: "input",
  Agent: "input",
  Research: "input",
  Meetings: "input",
  Jobs: "scroll",
  Integrations: "scroll",
  Config: "input",
};
