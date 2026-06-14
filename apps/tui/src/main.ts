import {
  BoxRenderable,
  InputRenderable,
  InputRenderableEvents,
  ScrollBoxRenderable,
  TabSelectRenderable,
  TabSelectRenderableEvents,
  TextRenderable,
  createCliRenderer,
} from "@opentui/core";
import { readFileSync } from "fs";
import { homedir } from "os";
import { join } from "path";

interface Ticket {
  id: string;
  project_id: string | null;
  title: string;
  description: string;
  status: string;
  kanban_column: string;
  kanban_position: number;
  note_path: string | null;
}

interface KanbanBoard {
  [column: string]: Ticket[];
}

interface Job {
  name: string;
  workflow_name: string;
  schedule: string;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
}

interface JobRun {
  id: string;
  job_name: string;
  status: string;
  workflow_run_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

interface MessageMetadata {
  [key: string]: unknown;
}

interface SessionMessage {
  id: string;
  session_id: string;
  role: string;
  content: string;
  metadata: MessageMetadata;
  created_at: string;
}

interface SessionRecord {
  id: string;
  mode: "chat" | "agent";
  title: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  messages: SessionMessage[];
}

interface SessionSendResponse {
  session: SessionRecord;
  assistant: SessionMessage;
  sources?: ResearchSource[];
  commands?: Array<{
    command: string;
    exit_code: number;
    stdout: string;
    stderr: string;
    created_id: string | null;
  }>;
}

interface ResearchSource {
  title: string;
  url: string;
}

interface ResearchRunResult {
  note_path: string;
  summary: string;
  sources: ResearchSource[];
  workflow_run_id?: string;
  status?: string;
  created_at?: string;
}

interface HealthResponse {
  status: string;
  vault_path?: string;
}

interface Banner {
  kind: "success" | "error" | "info";
  text: string;
}

type PageName = "Tickets" | "Chat" | "Agent" | "Research" | "Jobs" | "Config";

const PAGE_NAMES: PageName[] = ["Tickets", "Chat", "Agent", "Research", "Jobs", "Config"];
const PAGE_DESCRIPTIONS: Record<PageName, string> = {
  Tickets: "Create tickets and inspect the board",
  Chat: "Ask questions over local Nina context",
  Agent: "Natural language that can auto-run Nina commands",
  Research: "Research a topic and write an Obsidian note",
  Jobs: "Inspect scheduled workflows and recent runs",
  Config: "Local paths, auth, and runtime settings",
};
const PAGE_ACCENTS: Record<PageName, string> = {
  Tickets: "#22c55e",
  Chat: "#22d3ee",
  Agent: "#f97316",
  Research: "#eab308",
  Jobs: "#60a5fa",
  Config: "#94a3b8",
};
const PAGE_HELP: Record<PageName, string> = {
  Tickets: "Esc returns to the tab strip. Use Enter to create a ticket from the prompt. Ctrl+L refreshes the page.",
  Chat: "Esc returns to the tab strip. Enter sends the prompt. Ctrl+L refreshes the page.",
  Agent: "Esc returns to the tab strip. Enter sends the prompt and may execute Nina commands automatically.",
  Research: "Esc returns to the tab strip. Enter runs OpenAI web research and writes a note into Obsidian.",
  Jobs: "Esc returns to the tab strip. Ctrl+L refreshes the page.",
  Config: "Esc returns to the tab strip. Ctrl+L refreshes the page. Ctrl+C quits.",
};
const PAGE_INTRO: Record<PageName, string> = {
  Tickets: "Tickets are first-class aliases over Nina tasks. Use the prompt below for quick ticket creation, or use Agent mode for natural language and command execution.",
  Chat: "Chat mode answers questions with LLM-backed Obsidian context. It does not run commands.",
  Agent: "Agent mode can plan and auto-run Nina commands only. It is intended for natural-language task creation and other safe Nina operations.",
  Research: "Research mode uses OpenAI web search and writes a summary-plus-links note into your Obsidian vault.",
  Jobs: "Jobs execute Nina workflows on a schedule and keep their run history in SQLite.",
  Config: "This view reflects the local runtime wiring that the daemon and CLI use today.",
};
const COLUMN_ORDER = ["Backlog", "Todo", "Doing", "Review", "Done"];
const THEME = {
  background: "#0b0f14",
  panel: "#121821",
  panelAlt: "#161d28",
  border: "#334155",
  text: "#e5e7eb",
  subtle: "#94a3b8",
  danger: "#ef4444",
  success: "#22c55e",
  accent: "#22d3ee",
};

function getConfigDir(): string {
  const envDir = process.env.NINA_CONFIG_DIR;
  return envDir ? envDir : join(homedir(), ".nina", "default");
}

function getToken(): string {
  try {
    return readFileSync(join(getConfigDir(), "token"), "utf-8").trim();
  } catch {
    return "";
  }
}

async function fetchHealth(): Promise<HealthResponse> {
  try {
    const resp = await fetch("http://127.0.0.1:8765/health");
    if (!resp.ok) {
      return { status: "offline" };
    }
    return (await resp.json()) as HealthResponse;
  } catch {
    return { status: "offline" };
  }
}

async function apiFetch<T>(token: string, path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const resp = await fetch(`http://127.0.0.1:8765${path}`, {
    ...init,
    headers,
  });
  if (!resp.ok) {
    const text = await resp.text();
    let detail = resp.statusText;
    try {
      const body = JSON.parse(text) as { detail?: string };
      detail = body.detail || detail;
    } catch {
      detail = text || detail;
    }
    throw new Error(detail);
  }
  return (await resp.json()) as T;
}

function emptyBanner(): Banner | null {
  return null;
}

function clearChildren(container: BoxRenderable): void {
  for (const child of [...container.getChildren()]) {
    container.remove(child.id);
    child.destroyRecursively();
  }
}

function accentForPage(page: PageName): string {
  return PAGE_ACCENTS[page];
}

function roleAccent(role: string, page: PageName): string {
  if (role === "user") {
    return "#60a5fa";
  }
  if (role === "assistant") {
    return page === "Agent" ? accentForPage(page) : "#22c55e";
  }
  if (role === "tool") {
    return "#f59e0b";
  }
  return "#94a3b8";
}

function roleTitle(role: string): string {
  if (role === "user") {
    return "User";
  }
  if (role === "assistant") {
    return "Assistant";
  }
  if (role === "tool") {
    return "Tool";
  }
  return role;
}

function normalizeLines(text: string): string {
  const trimmed = text.trim();
  return trimmed.length > 0 ? trimmed : "(empty)";
}

function buildCard(
  renderer: Awaited<ReturnType<typeof createCliRenderer>>,
  title: string,
  accent: string,
  body: string,
  bodyColor: string = THEME.text,
): BoxRenderable {
  const card = new BoxRenderable(renderer, {
    border: true,
    borderColor: accent,
    title,
    titleColor: accent,
    backgroundColor: THEME.panelAlt,
    flexDirection: "column",
    padding: 1,
    gap: 1,
    shouldFill: true,
  });
  card.add(
    new TextRenderable(renderer, {
      content: normalizeLines(body),
      fg: bodyColor,
      wrapMode: "word",
      truncate: false,
    }),
  );
  return card;
}

function parseTicketDraft(value: string): { title: string; description: string } {
  const trimmed = value.trim();
  const separator = trimmed.indexOf(" | ");
  if (separator >= 0) {
    return {
      title: trimmed.slice(0, separator).trim(),
      description: trimmed.slice(separator + 3).trim(),
    };
  }
  return { title: trimmed, description: "" };
}

function formatTime(value: string | null): string {
  return value && value.length > 0 ? value : "never";
}

function orderedColumns(board: KanbanBoard): string[] {
  const seen = new Set<string>();
  const columns: string[] = [];
  for (const name of COLUMN_ORDER) {
    if (board[name]) {
      columns.push(name);
      seen.add(name);
    }
  }
  for (const name of Object.keys(board).sort()) {
    if (!seen.has(name)) {
      columns.push(name);
    }
  }
  return columns;
}

async function main(): Promise<void> {
  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    console.error("Nina TUI requires an interactive terminal. Run `make tui` or `nina tui` directly in a TTY.");
    process.exit(1);
  }

  const token = getToken();
  const health = await fetchHealth();
  const renderer = await createCliRenderer({
    exitOnCtrlC: true,
    screenMode: "alternate-screen",
    backgroundColor: THEME.background,
  });

  const shell = new BoxRenderable(renderer, {
    flexDirection: "column",
    padding: 1,
    gap: 1,
    flexGrow: 1,
    backgroundColor: THEME.background,
  });
  renderer.root.add(shell);

  const tabs = new TabSelectRenderable(renderer, {
    options: PAGE_NAMES.map((name) => ({ name, description: PAGE_DESCRIPTIONS[name] })),
    showUnderline: true,
    showDescription: false,
    tabWidth: 12,
    backgroundColor: THEME.background,
    textColor: THEME.text,
    focusedBackgroundColor: THEME.panel,
    focusedTextColor: THEME.text,
    selectedBackgroundColor: THEME.panelAlt,
    selectedTextColor: accentForPage("Tickets"),
    selectedDescriptionColor: THEME.subtle,
  });
  shell.add(tabs);

  const content = new BoxRenderable(renderer, {
    flexDirection: "column",
    flexGrow: 1,
    backgroundColor: THEME.background,
  });
  shell.add(content);

  const state: {
    currentPage: PageName;
    banner: Banner | null;
    lastError: string | null;
    kanban: KanbanBoard | null;
    jobs: Job[];
    jobRuns: JobRun[];
    chatSession: SessionRecord | null;
    agentSession: SessionRecord | null;
    researchReport: ResearchRunResult | null;
  } = {
    currentPage: "Tickets",
    banner: health.status === "offline" ? { kind: "error", text: "Daemon is offline. Start it with `nina daemon start` or `make dev`." } : null,
    lastError: null,
    kanban: null,
    jobs: [],
    jobRuns: [],
    chatSession: null,
    agentSession: null,
    researchReport: null,
  };

  let activeInput: InputRenderable | null = null;

  function bannerColor(banner: Banner): string {
    if (banner.kind === "success") {
      return THEME.success;
    }
    if (banner.kind === "error") {
      return THEME.danger;
    }
    return THEME.accent;
  }

  function addBanner(pageRoot: BoxRenderable): void {
    if (state.banner) {
      pageRoot.add(
        buildCard(renderer, state.banner.kind === "error" ? "Error" : "Status", bannerColor(state.banner), state.banner.text),
      );
    }
    if (state.lastError) {
      pageRoot.add(buildCard(renderer, "Request failed", THEME.danger, state.lastError, THEME.danger));
    }
  }

  function addIntro(pageRoot: BoxRenderable, page: PageName): void {
    pageRoot.add(
      new TextRenderable(renderer, {
        content: `${PAGE_INTRO[page]}\n${PAGE_HELP[page]}`,
        fg: THEME.subtle,
        wrapMode: "word",
        truncate: false,
      }),
    );
  }

  function makeScrollArea(pageRoot: BoxRenderable, accent: string): ScrollBoxRenderable {
    const scroll = new ScrollBoxRenderable(renderer, {
      flexGrow: 1,
      border: true,
      borderColor: accent,
      backgroundColor: THEME.background,
      stickyScroll: true,
      stickyStart: "bottom",
      viewportCulling: true,
      padding: 1,
    });
    pageRoot.add(scroll);
    return scroll;
  }

  function makeInputSection(
    pageRoot: BoxRenderable,
    title: string,
    placeholder: string,
    accent: string,
  ): InputRenderable {
    const frame = new BoxRenderable(renderer, {
      border: true,
      borderColor: accent,
      title,
      titleColor: accent,
      backgroundColor: THEME.panel,
      flexDirection: "column",
      padding: 1,
      gap: 1,
    });
    const input = new InputRenderable(renderer, {
      placeholder,
      minLength: 1,
      flexGrow: 1,
      backgroundColor: THEME.panel,
      textColor: THEME.text,
      focusedBackgroundColor: THEME.panelAlt,
      focusedTextColor: THEME.text,
    });
    frame.add(input);
    pageRoot.add(frame);
    return input;
  }

  function renderTicketsPage(pageRoot: BoxRenderable): void {
    const scroll = makeScrollArea(pageRoot, accentForPage("Tickets"));
    if (!token) {
      scroll.add(
        buildCard(
          renderer,
          "No token",
          THEME.danger,
          "Run `nina init` first so the TUI can talk to the daemon.",
          THEME.danger,
        ),
      );
    } else if (!state.kanban) {
      scroll.add(buildCard(renderer, "No board", accentForPage("Tickets"), "No kanban board data was loaded."));
    } else {
      for (const column of orderedColumns(state.kanban)) {
        const tasks = state.kanban[column] ?? [];
        const body =
          tasks.length === 0
            ? "(empty)"
            : tasks
                .map((task) => {
                  const description = task.description.trim();
                  const note = task.note_path ? `\n  note: ${task.note_path}` : "";
                  const extra = description ? `\n  ${description}` : "";
                  return `- ${task.title} [${task.status}]${extra}${note}`;
                })
                .join("\n\n");
        scroll.add(buildCard(renderer, `${column} (${tasks.length})`, accentForPage("Tickets"), body));
      }
    }

    const input = makeInputSection(
      pageRoot,
      "Create ticket",
      "Ticket title | description",
      accentForPage("Tickets"),
    );
    activeInput = input;
    input.on(InputRenderableEvents.ENTER, (value: string) => {
      void (async () => {
        try {
          state.banner = null;
          state.lastError = null;
          const draft = parseTicketDraft(value);
          if (!draft.title) {
            return;
          }
          input.value = "";
          const created = await apiFetch<Ticket>(token, "/tickets", {
            method: "POST",
            body: JSON.stringify({ title: draft.title, description: draft.description }),
          });
          state.banner = { kind: "success", text: `Created ticket ${created.id}` };
          await refreshTickets();
          renderPage("Tickets");
        } catch (error) {
          state.lastError = error instanceof Error ? error.message : String(error);
          renderPage("Tickets");
        }
      })();
    });
  }

  function renderChatPage(pageRoot: BoxRenderable): void {
    const scroll = makeScrollArea(pageRoot, accentForPage("Chat"));
    if (!state.chatSession) {
      scroll.add(buildCard(renderer, "No session", accentForPage("Chat"), "Open the page again or send a prompt to create a chat session."));
    } else if (state.chatSession.messages.length === 0) {
      scroll.add(buildCard(renderer, "Empty chat", accentForPage("Chat"), "Send a prompt to start the conversation."));
    } else {
      for (const message of state.chatSession.messages) {
        scroll.add(buildMessageCard(message, "Chat"));
      }
    }

    const input = makeInputSection(pageRoot, "Chat prompt", "Ask Nina a question about your vault", accentForPage("Chat"));
    activeInput = input;
    input.on(InputRenderableEvents.ENTER, (value: string) => {
      void sendChatPrompt(value, input);
    });
  }

  function renderAgentPage(pageRoot: BoxRenderable): void {
    const scroll = makeScrollArea(pageRoot, accentForPage("Agent"));
    if (!state.agentSession) {
      scroll.add(buildCard(renderer, "No session", accentForPage("Agent"), "Send a prompt to create an agent session."));
    } else if (state.agentSession.messages.length === 0) {
      scroll.add(buildCard(renderer, "Empty agent session", accentForPage("Agent"), "Describe a ticket or task and the agent will plan and run Nina commands."));
    } else {
      for (const message of state.agentSession.messages) {
        scroll.add(buildMessageCard(message, "Agent"));
      }
    }

    const input = makeInputSection(
      pageRoot,
      "Agent prompt",
      "Create a ticket, move it, or ask the agent to run Nina commands",
      accentForPage("Agent"),
    );
    activeInput = input;
    input.on(InputRenderableEvents.ENTER, (value: string) => {
      void sendAgentPrompt(value, input);
    });
  }

  function renderResearchPage(pageRoot: BoxRenderable): void {
    const scroll = makeScrollArea(pageRoot, accentForPage("Research"));
    if (!state.researchReport) {
      scroll.add(buildCard(renderer, "No research yet", accentForPage("Research"), "Research a topic to create a summary-plus-links note in Obsidian."));
    } else {
      const sourceLines =
        state.researchReport.sources.length === 0
          ? "- No sources captured"
          : state.researchReport.sources.map((source) => `- ${source.title} -> ${source.url}`).join("\n");
      scroll.add(
        buildCard(
          renderer,
          `Research note: ${state.researchReport.note_path}`,
          accentForPage("Research"),
          `${state.researchReport.summary}\n\nSources:\n${sourceLines}`,
        ),
      );
    }

    const input = makeInputSection(pageRoot, "Research topic", "Research a topic and write a note into Obsidian", accentForPage("Research"));
    activeInput = input;
    input.on(InputRenderableEvents.ENTER, (value: string) => {
      void runResearch(value, input);
    });
  }

  function renderJobsPage(pageRoot: BoxRenderable): void {
    const scroll = makeScrollArea(pageRoot, accentForPage("Jobs"));
    if (state.jobs.length === 0) {
      scroll.add(buildCard(renderer, "No jobs", accentForPage("Jobs"), "No scheduled jobs were returned by the daemon."));
    } else {
      for (const job of state.jobs) {
        scroll.add(
          buildCard(
            renderer,
            job.name,
            accentForPage("Jobs"),
            [
              `Workflow: ${job.workflow_name}`,
              `Schedule: ${job.schedule}`,
              `Enabled: ${job.enabled ? "yes" : "no"}`,
              `Last run: ${formatTime(job.last_run_at)}`,
              `Next run: ${formatTime(job.next_run_at)}`,
            ].join("\n"),
          ),
        );
      }
      if (state.jobRuns.length > 0) {
        for (const run of state.jobRuns) {
          scroll.add(
            buildCard(
              renderer,
              `Run: ${run.job_name}`,
              "#94a3b8",
              [
                `Status: ${run.status}`,
                `Started: ${formatTime(run.started_at)}`,
                `Completed: ${formatTime(run.completed_at)}`,
                run.error ? `Error: ${run.error}` : "",
              ]
                .filter((line) => line.length > 0)
                .join("\n"),
              THEME.subtle,
            ),
          );
        }
      }
    }
  }

  function renderConfigPage(pageRoot: BoxRenderable): void {
    const body = [
      `Config dir: ${getConfigDir()}`,
      `Token file: ${join(getConfigDir(), "token")}`,
      `Vault path: ${process.env.NINA_VAULT_PATH || join(getConfigDir(), "vault")}`,
      `Database path: ${process.env.NINA_DATABASE_PATH || join(getConfigDir(), "nina.db")}`,
      `Daemon health: ${health.status}`,
      `LLM provider: ${process.env.NINA_LLM_PROVIDER || "codex"}`,
      `Research provider: ${process.env.NINA_RESEARCH_PROVIDER || "openai_web"}`,
      `OPENAI_API_KEY: ${process.env.OPENAI_API_KEY ? "set" : "unset"}`,
      `Codex auth file: ${process.env.CODEX_AUTH_FILE || join(homedir(), ".codex", "auth.json")}`,
      "",
      "Ticket mode uses /tickets over the same task storage used by the board.",
      "Research mode writes summary-plus-links notes into Research/YYYY-MM-DD - <topic>.md.",
      "",
      "Hotkeys: Esc focuses the tab strip, Ctrl+L refreshes the current page, Ctrl+C quits.",
    ].join("\n");
    pageRoot.add(buildCard(renderer, "Runtime config", accentForPage("Config"), body, THEME.text));
  }

  function renderMessageCard(message: SessionMessage, page: "Chat" | "Agent"): BoxRenderable {
    const accent = roleAccent(message.role, page);
    let body = normalizeLines(message.content);
    const metadata = message.metadata;
    if (page === "Chat" && message.role === "assistant") {
      const sources = Array.isArray(metadata.sources) ? (metadata.sources as ResearchSource[]) : [];
      if (sources.length > 0) {
        body += `\n\nSources:\n${sources.map((source) => `- ${source.title} -> ${source.url}`).join("\n")}`;
      }
    }
    if (page === "Agent" && message.role === "assistant") {
      const results = Array.isArray(metadata.results) ? (metadata.results as Array<{ command: string; exit_code: number }>) : [];
      if (results.length > 0) {
        body += `\n\nExecuted ${results.length} Nina command(s).`;
      }
    }
    return buildCard(renderer, roleTitle(message.role), accent, body, message.role === "tool" ? THEME.subtle : THEME.text);
  }

  async function loadConversationSession(mode: "chat" | "agent", existing: SessionRecord | null, title: string): Promise<SessionRecord> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    if (existing) {
      return await apiFetch<SessionRecord>(token, `/sessions/${existing.id}`);
    }
    const sessions = await apiFetch<SessionRecord[]>(token, `/sessions?mode=${mode}`);
    if (sessions.length > 0) {
      return await apiFetch<SessionRecord>(token, `/sessions/${sessions[0].id}`);
    }
    return await apiFetch<SessionRecord>(token, "/sessions", {
      method: "POST",
      body: JSON.stringify({ mode, title }),
    });
  }

  async function refreshTickets(): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    state.kanban = await apiFetch<KanbanBoard>(token, "/kanban");
  }

  async function refreshJobs(): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    state.jobs = await apiFetch<Job[]>(token, "/jobs");
    state.jobRuns = await apiFetch<JobRun[]>(token, "/job-runs?limit=8");
  }

  async function sendChatPrompt(value: string, input: InputRenderable): Promise<void> {
    try {
      const prompt = value.trim();
      if (!prompt) {
        return;
      }
      state.banner = null;
      state.lastError = null;
      input.value = "";
      state.chatSession = await loadConversationSession("chat", state.chatSession, "Chat");
      const response = await apiFetch<SessionSendResponse>(token, `/sessions/${state.chatSession.id}/messages`, {
        method: "POST",
        body: JSON.stringify({ content: prompt }),
      });
      state.chatSession = response.session;
      renderPage("Chat");
    } catch (error) {
      state.lastError = error instanceof Error ? error.message : String(error);
      renderPage("Chat");
    }
  }

  async function sendAgentPrompt(value: string, input: InputRenderable): Promise<void> {
    try {
      const prompt = value.trim();
      if (!prompt) {
        return;
      }
      state.banner = null;
      state.lastError = null;
      input.value = "";
      state.agentSession = await loadConversationSession("agent", state.agentSession, "Agent");
      const response = await apiFetch<SessionSendResponse>(token, `/sessions/${state.agentSession.id}/messages`, {
        method: "POST",
        body: JSON.stringify({ content: prompt }),
      });
      state.agentSession = response.session;
      state.banner = { kind: "success", text: response.assistant.content };
      renderPage("Agent");
    } catch (error) {
      state.lastError = error instanceof Error ? error.message : String(error);
      renderPage("Agent");
    }
  }

  async function runResearch(value: string, input: InputRenderable): Promise<void> {
    try {
      const topic = value.trim();
      if (!topic) {
        return;
      }
      state.banner = null;
      state.lastError = null;
      input.value = "";
      const report = await apiFetch<ResearchRunResult>(token, "/research/run", {
        method: "POST",
        body: JSON.stringify({ topic }),
      });
      state.researchReport = report;
      state.banner = { kind: "success", text: `Research note written to ${report.note_path}` };
      renderPage("Research");
    } catch (error) {
      state.lastError = error instanceof Error ? error.message : String(error);
      renderPage("Research");
    }
  }

  function renderPage(page: PageName): void {
    state.currentPage = page;
    clearChildren(content);
    activeInput = null;

    const pageRoot = new BoxRenderable(renderer, {
      flexDirection: "column",
      flexGrow: 1,
      border: true,
      borderColor: accentForPage(page),
      title: page,
      titleColor: accentForPage(page),
      backgroundColor: THEME.panel,
      padding: 1,
      gap: 1,
      shouldFill: true,
    });
    content.add(pageRoot);

    addBanner(pageRoot);
    addIntro(pageRoot, page);

    switch (page) {
      case "Tickets":
        renderTicketsPage(pageRoot);
        break;
      case "Chat":
        renderChatPage(pageRoot);
        break;
      case "Agent":
        renderAgentPage(pageRoot);
        break;
      case "Research":
        renderResearchPage(pageRoot);
        break;
      case "Jobs":
        renderJobsPage(pageRoot);
        break;
      case "Config":
        renderConfigPage(pageRoot);
        break;
    }

    const inputToFocus = activeInput;
    process.nextTick(() => {
      if (inputToFocus) {
        inputToFocus.focus();
      } else {
        tabs.focus();
      }
    });
  }

  async function loadPageData(page: PageName): Promise<void> {
    state.banner = null;
    state.lastError = null;
    switch (page) {
      case "Tickets":
        await refreshTickets();
        break;
      case "Chat":
        state.chatSession = await loadConversationSession("chat", state.chatSession, "Chat");
        break;
      case "Agent":
        state.agentSession = await loadConversationSession("agent", state.agentSession, "Agent");
        break;
      case "Research":
        break;
      case "Jobs":
        await refreshJobs();
        break;
      case "Config":
        break;
    }
  }

  async function switchPage(page: PageName): Promise<void> {
    try {
      await loadPageData(page);
    } catch (error) {
      state.lastError = error instanceof Error ? error.message : String(error);
    }
    renderPage(page);
  }

  tabs.on(TabSelectRenderableEvents.SELECTION_CHANGED, (_index: number, option: { name: string } | null) => {
    if (!option) {
      return;
    }
    void switchPage(option.name as PageName);
  });

  renderer.keyInput.on("keypress", (key: { name: string; ctrl: boolean; preventDefault: () => void; stopPropagation: () => void }) => {
    if (key.name === "escape" || key.name === "esc") {
      if (activeInput) {
        activeInput.blur();
      }
      tabs.focus();
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (key.ctrl && key.name === "l") {
      void switchPage(state.currentPage);
      key.preventDefault();
      key.stopPropagation();
    }
  });

  await switchPage(state.currentPage);
}

main().catch((err) => {
  console.error("TUI error:", err);
  process.exit(1);
});
