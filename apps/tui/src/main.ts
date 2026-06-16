import {
  BoxRenderable,
  InputRenderable,
  InputRenderableEvents,
  ScrollBoxRenderable,
  SelectRenderable,
  SelectRenderableEvents,
  KeyEvent,
  MouseEvent as TuiMouseEvent,
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
  created_at: string;
  updated_at: string;
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
  sources?: VaultSource[];
  tools_used?: ToolInvocation[];
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

interface VaultSource {
  path: string;
  title?: string;
  nina_type?: string;
  snippet?: string;
}

interface ToolInvocation {
  id: string;
  name: string;
  preview?: string;
  arguments?: Record<string, unknown>;
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
  profile?: string;
  vault_path?: string;
}

interface RuntimeState {
  profile?: string;
  config_dir?: string;
  daemon_host?: string;
  daemon_port?: number;
}

interface ConfigSnapshot {
  profile: string;
  config_dir: string;
  config_path: string;
  vault_path: string;
  database_path: string;
  daemon_host: string;
  daemon_port: number;
  llm: {
    provider: string;
    model: string;
  };
  research: {
    provider: string;
    model: string;
  };
  scheduler: {
    daily_summary_time: string;
  };
  transcription: {
    backend: string;
    model: string;
    device: string;
    compute_type: string;
    language: string | null;
  };
  meetings: {
    default_source: string;
    auto_summarize: boolean;
    sample_rate: number;
    channels: number;
    open_command: string;
    play_command: string;
    default_gain: number;
    auto_normalize: boolean;
    normalize_target_dbfs: number;
    noise_reduction: string;
  };
  log_level: string;
}

interface Meeting {
  id: string;
  title: string;
  status: string;
  source: string;
  device_name: string | null;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
  audio_path: string;
  audio_size_bytes: number | null;
  audio_format: string;
  sample_rate: number;
  channels: number;
  transcript_path: string | null;
  summary_path: string | null;
  workflow_run_id: string | null;
  error: string | null;
  note_path: string | null;
  created_at: string;
  updated_at: string;
}

interface ConfigUpdateResponse {
  config: ConfigSnapshot;
  changed_fields: string[];
  restart_required: boolean;
}

type ConfigFieldKey =
  | "vault_path"
  | "database_path"
  | "daemon_host"
  | "daemon_port"
  | "log_level"
  | "llm.provider"
  | "llm.model"
  | "scheduler.daily_summary_time"
  | "transcription.backend"
  | "transcription.model"
  | "transcription.device"
  | "transcription.compute_type"
  | "transcription.language"
  | "meetings.default_source"
  | "meetings.auto_summarize"
  | "meetings.sample_rate"
  | "meetings.channels"
  | "meetings.default_gain"
  | "meetings.auto_normalize"
  | "meetings.normalize_target_dbfs"
  | "meetings.noise_reduction";

interface ConfigFieldDefinition {
  key: ConfigFieldKey;
  label: string;
  description: string;
  restartRequired: boolean;
  getValue: (config: ConfigSnapshot) => string;
  buildPatch: (value: string) => Record<string, unknown>;
}

interface Banner {
  kind: "success" | "error" | "info";
  text: string;
}

type PageName = "Tickets" | "Chat" | "Agent" | "Research" | "Jobs" | "Meetings" | "Config";
type PageFocusTarget = "tabs" | "scroll" | "input" | "select";
type MainPageFocusTarget = Exclude<PageFocusTarget, "tabs">;

const PAGE_NAMES: PageName[] = [
  "Tickets",
  "Chat",
  "Agent",
  "Research",
  "Meetings",
  "Jobs",
  "Config",
];
const PAGE_DESCRIPTIONS: Record<PageName, string> = {
  Tickets: "Create tickets and inspect the board",
  Chat: "Ask questions over local Nina context",
  Agent: "Natural language that can auto-run Nina commands",
  Research: "Research a topic and write an Obsidian note",
  Meetings: "Record meetings, transcribe, and summarize",
  Jobs: "Inspect scheduled workflows and recent runs",
  Config: "Vault, database, daemon, and runtime settings",
};
const PAGE_ACCENTS: Record<PageName, string> = {
  Tickets: "#22c55e",
  Chat: "#22d3ee",
  Agent: "#f97316",
  Research: "#eab308",
  Meetings: "#a855f7",
  Jobs: "#60a5fa",
  Config: "#94a3b8",
};
const PAGE_HELP: Record<PageName, string> = {
  Tickets: "Esc returns to the tab strip. Tab and Shift+Tab change pages. Ctrl+Up/Down selects a ticket. Ctrl+Left/Right moves the selected ticket between columns. Ctrl+E toggles the detail view. Enter creates a ticket. Ctrl+D deletes a ticket. Ctrl+A archives a ticket. PageUp/PageDown scroll the kanban. Ctrl+R refreshes the page.",
  Chat: "Esc returns to the tab strip. Click a tab to switch pages. Tab and Shift+Tab change pages. Click the history to focus it or the prompt to type. F6 toggles between the history and prompt. Enter sends the prompt. Use @path/to/note.md in the prompt to attach a note. While waiting, a loading card shows elapsed time. Ctrl+Q clears the chat and starts a new context. Ctrl+. cancels the running response. PageUp/PageDown scroll the history; End jumps to the bottom. Ctrl+R refreshes the page.",
  Agent: "Esc returns to the tab strip. Click a tab to switch pages. Tab and Shift+Tab change pages. Click the history to focus it or the prompt to type. F6 toggles between the history and prompt. Enter sends the prompt and may execute tool calls automatically. While waiting, a loading card shows elapsed time. Ctrl+. cancels the running response. PageUp/PageDown scroll the history; End jumps to the bottom.",
  Research: "Esc returns to the tab strip. Click a tab to switch pages. Tab and Shift+Tab change pages. Click the history to focus it or the prompt to type. F6 toggles between the history and prompt. Enter runs OpenAI web research and writes a note into Obsidian. While waiting, a loading card shows elapsed time. PageUp/PageDown scroll the report.",
  Meetings: "Esc returns to the tab strip. Tab and Shift+Tab change pages. Up/Down moves the selection. Type a title and press Enter to start a recording. All other actions use Ctrl so the text input does not swallow them: Ctrl+T transcribe, Ctrl+Y summarize, Ctrl+X stop active recording, Ctrl+O open in Obsidian, Ctrl+P play audio, Ctrl+D delete. PageUp/PageDown scroll the list. Ctrl+R refreshes the page.",
  Jobs: "Esc returns to the tab strip. Click a tab to switch pages. Tab and Shift+Tab change pages. Click the history to focus it. F6 toggles between the history and the tab strip. PageUp/PageDown and Home/End scroll the history. Ctrl+R refreshes the page.",
  Config: "Esc returns to the tab strip. Click a tab to switch pages. Click the list or the value field to focus it. F6 toggles between the editable list and the value field. Up and Down change the selected setting. Enter saves the current value. Tab and Shift+Tab change pages. Ctrl+R refreshes the page. Ctrl+C quits.",
};
const PAGE_INTRO: Record<PageName, string> = {
  Tickets: "Tickets are first-class aliases over Nina tasks. Use the prompt below for quick ticket creation, or use Agent mode for natural language and command execution.",
  Chat: "Chat mode answers questions with LLM-backed Obsidian context via tool calls. Use @path/to/note.md in the prompt to attach a note. It does not run commands or write to the vault.",
  Agent: "Agent mode can plan and execute tool calls (read + write) against the vault, kanban, and jobs. It is intended for natural-language task creation and other safe Nina operations.",
  Research: "Research mode uses OpenAI web search and writes a summary-plus-links note into your Obsidian vault.",
  Meetings: "Meetings are recorded through the daemon-backed CLI or TUI. Each recording creates a Meetings/<date> - <title>.md note in Obsidian. Transcription and summarization are workflows that read the same audio file.",
  Jobs: "Jobs execute Nina workflows on a schedule and keep their run history in SQLite.",
  Config: "This view lets you inspect and edit the config file that the daemon and CLI read.",
};
const PAGE_DEFAULT_FOCUS: Record<PageName, MainPageFocusTarget> = {
  Tickets: "input",
  Chat: "input",
  Agent: "input",
  Research: "input",
  Meetings: "input",
  Jobs: "scroll",
  Config: "input",
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

function getTabWindow(tabs: TabSelectRenderable): { scrollOffset: number; maxVisibleTabs: number } {
  const tabWidth = tabs.getTabWidth();
  const maxVisibleTabs = Math.max(1, Math.floor(tabs.width / tabWidth));
  const selectedIndex = tabs.getSelectedIndex();
  const halfVisible = Math.floor(maxVisibleTabs / 2);
  const maxScrollOffset = Math.max(0, tabs.options.length - maxVisibleTabs);
  const scrollOffset = Math.max(0, Math.min(selectedIndex - halfVisible, maxScrollOffset));
  return { scrollOffset, maxVisibleTabs };
}

function moveTabSelection(tabs: TabSelectRenderable, direction: 1 | -1): void {
  const tabCount = tabs.options.length;
  if (tabCount === 0) {
    return;
  }
  const nextIndex = (tabs.getSelectedIndex() + direction + tabCount) % tabCount;
  tabs.setSelectedIndex(nextIndex);
}

function resolveTabIndexFromMouse(tabs: TabSelectRenderable, event: TuiMouseEvent): number | null {
  if (event.button !== 0) {
    return null;
  }

  const tabCount = tabs.options.length;
  if (tabCount === 0) {
    return null;
  }

  const relativeX = event.x - tabs.screenX;
  if (relativeX < 0 || relativeX >= tabs.width) {
    return null;
  }

  const { scrollOffset, maxVisibleTabs } = getTabWindow(tabs);
  const hasOverflow = tabCount > maxVisibleTabs;

  if (tabs.showScrollArrows && hasOverflow) {
    if (relativeX === 0 && scrollOffset > 0) {
      return Math.max(0, tabs.getSelectedIndex() - 1);
    }
    if (relativeX === tabs.width - 1 && scrollOffset + maxVisibleTabs < tabCount) {
      return Math.min(tabCount - 1, tabs.getSelectedIndex() + 1);
    }
  }

  const visibleTabCount = Math.min(tabCount - scrollOffset, maxVisibleTabs);
  const tabColumn = Math.min(Math.floor(relativeX / tabs.getTabWidth()), visibleTabCount - 1);
  return scrollOffset + Math.max(0, tabColumn);
}

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

function getApiBase(): string {
  const configDir = getConfigDir();
  const runtimePath = join(configDir, "daemon.json");
  try {
    const runtime = JSON.parse(readFileSync(runtimePath, "utf-8")) as RuntimeState;
    if (runtime.daemon_host && runtime.daemon_port) {
      return `http://${runtime.daemon_host}:${runtime.daemon_port}`;
    }
  } catch {
    try {
      const config = readFileSync(join(configDir, "config.yaml"), "utf-8");
      const hostMatch = config.match(/^daemon_host:\s*(.+)$/m);
      const portMatch = config.match(/^daemon_port:\s*(\d+)$/m);
      if (hostMatch && portMatch) {
        return `http://${hostMatch[1].trim()}:${Number.parseInt(portMatch[1], 10)}`;
      }
    } catch {
      // Fall back to the default local daemon address below.
    }
  }
  return "http://127.0.0.1:8765";
}

async function fetchHealth(): Promise<HealthResponse> {
  try {
    const resp = await fetch(`${getApiBase()}/health`);
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
  const resp = await fetch(`${getApiBase()}${path}`, {
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

function parseTicketEdit(value: string): { title: string; description: string; status: string } {
  const trimmed = value.trim();
  const parts = trimmed.split(" | ");
  if (parts.length >= 3) {
    return { title: parts[0].trim(), description: parts[1].trim(), status: parts[2].trim() };
  }
  if (parts.length === 2) {
    return { title: parts[0].trim(), description: parts[1].trim(), status: "" };
  }
  return { title: trimmed, description: "", status: "" };
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

const CONFIG_FIELDS: ConfigFieldDefinition[] = [
  {
    key: "vault_path",
    label: "Vault path",
    description: "Obsidian vault root",
    restartRequired: false,
    getValue: (config) => config.vault_path,
    buildPatch: (value) => ({ vault_path: value }),
  },
  {
    key: "database_path",
    label: "Database path",
    description: "SQLite database file",
    restartRequired: false,
    getValue: (config) => config.database_path,
    buildPatch: (value) => ({ database_path: value }),
  },
  {
    key: "daemon_host",
    label: "Daemon host",
    description: "Bind address on the next start",
    restartRequired: true,
    getValue: (config) => config.daemon_host,
    buildPatch: (value) => ({ daemon_host: value }),
  },
  {
    key: "daemon_port",
    label: "Daemon port",
    description: "Bind port on the next start",
    restartRequired: true,
    getValue: (config) => String(config.daemon_port),
    buildPatch: (value) => ({ daemon_port: Number.parseInt(value, 10) }),
  },
  {
    key: "log_level",
    label: "Log level",
    description: "Uvicorn log level on the next start",
    restartRequired: true,
    getValue: (config) => config.log_level,
    buildPatch: (value) => ({ log_level: value }),
  },
  {
    key: "llm.provider",
    label: "LLM provider",
    description: "LLM backend",
    restartRequired: false,
    getValue: (config) => config.llm.provider,
    buildPatch: (value) => ({ llm: { provider: value } }),
  },
  {
    key: "llm.model",
    label: "LLM model",
    description: "Model name",
    restartRequired: false,
    getValue: (config) => config.llm.model,
    buildPatch: (value) => ({ llm: { model: value } }),
  },
  {
    key: "scheduler.daily_summary_time",
    label: "Daily summary time",
    description: "Daily summary schedule",
    restartRequired: false,
    getValue: (config) => config.scheduler.daily_summary_time,
    buildPatch: (value) => ({ scheduler: { daily_summary_time: value } }),
  },
  {
    key: "transcription.backend",
    label: "Transcription backend",
    description: "local_whisper, whisper_cli, or null",
    restartRequired: false,
    getValue: (config) => config.transcription.backend,
    buildPatch: (value) => ({ transcription: { backend: value } }),
  },
  {
    key: "transcription.model",
    label: "Transcription model",
    description: "tiny | base | small | medium | large-v3",
    restartRequired: false,
    getValue: (config) => config.transcription.model,
    buildPatch: (value) => ({ transcription: { model: value } }),
  },
  {
    key: "transcription.device",
    label: "Transcription device",
    description: "cpu | cuda",
    restartRequired: false,
    getValue: (config) => config.transcription.device,
    buildPatch: (value) => ({ transcription: { device: value } }),
  },
  {
    key: "transcription.compute_type",
    label: "Transcription compute",
    description: "int8 | float16 | float32",
    restartRequired: false,
    getValue: (config) => config.transcription.compute_type,
    buildPatch: (value) => ({ transcription: { compute_type: value } }),
  },
  {
    key: "transcription.language",
    label: "Transcription language",
    description: "Language code or 'auto'",
    restartRequired: false,
    getValue: (config) => config.transcription.language ?? "auto",
    buildPatch: (value) => ({
      transcription: { language: value === "auto" ? null : value },
    }),
  },
  {
    key: "meetings.default_source",
    label: "Meetings default source",
    description: "mic | system | mixed",
    restartRequired: false,
    getValue: (config) => config.meetings.default_source,
    buildPatch: (value) => ({ meetings: { default_source: value } }),
  },
  {
    key: "meetings.sample_rate",
    label: "Meetings sample rate",
    description: "Sample rate in Hz",
    restartRequired: false,
    getValue: (config) => String(config.meetings.sample_rate),
    buildPatch: (value) => ({ meetings: { sample_rate: Number.parseInt(value, 10) } }),
  },
  {
    key: "meetings.channels",
    label: "Meetings channels",
    description: "1 or 2",
    restartRequired: false,
    getValue: (config) => String(config.meetings.channels),
    buildPatch: (value) => ({ meetings: { channels: Number.parseInt(value, 10) } }),
  },
  {
    key: "meetings.default_gain",
    label: "Meetings default gain",
    description: "Linear gain factor",
    restartRequired: false,
    getValue: (config) => String(config.meetings.default_gain),
    buildPatch: (value) => ({ meetings: { default_gain: Number.parseFloat(value) } }),
  },
  {
    key: "meetings.auto_normalize",
    label: "Meetings auto-normalize",
    description: "true | false",
    restartRequired: false,
    getValue: (config) => String(config.meetings.auto_normalize),
    buildPatch: (value) => ({
      meetings: { auto_normalize: value.toLowerCase() === "true" },
    }),
  },
  {
    key: "meetings.normalize_target_dbfs",
    label: "Normalize target dBFS",
    description: "Usually -3.0",
    restartRequired: false,
    getValue: (config) => String(config.meetings.normalize_target_dbfs),
    buildPatch: (value) => ({ meetings: { normalize_target_dbfs: Number.parseFloat(value) } }),
  },
  {
    key: "meetings.noise_reduction",
    label: "Meetings noise reduction",
    description: "off | ffmpeg",
    restartRequired: false,
    getValue: (config) => config.meetings.noise_reduction,
    buildPatch: (value) => ({ meetings: { noise_reduction: value } }),
  },
  {
    key: "meetings.auto_summarize",
    label: "Auto-summarize meetings",
    description: "true | false",
    restartRequired: false,
    getValue: (config) => String(config.meetings.auto_summarize),
    buildPatch: (value) => ({
      meetings: { auto_summarize: value.toLowerCase() === "true" },
    }),
  },
];

function getConfigFieldDefinition(key: ConfigFieldKey): ConfigFieldDefinition {
  return CONFIG_FIELDS.find((field) => field.key === key) ?? CONFIG_FIELDS[0];
}

async function main(): Promise<void> {
  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    console.error("Nina TUI requires an interactive terminal. Run `make tui` or `nina tui` directly in a TTY.");
    process.exit(1);
  }

  process.env.OPENTUI_NO_GRAPHICS = "1";

  const token = getToken();
  const health = await fetchHealth();
  const renderer = await createCliRenderer({
    exitOnCtrlC: true,
    screenMode: "alternate-screen",
    backgroundColor: THEME.background,
    useMouse: true,
    enableMouseMovement: true,
    useKittyKeyboard: null,
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
    onMouseDown() {
      setPageFocus(state.currentPage, "tabs");
      tabs.focus();
    },
    onMouseUp(event) {
      const tabIndex = resolveTabIndexFromMouse(tabs, event);
      if (tabIndex === null) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      tabs.setSelectedIndex(tabIndex);
    },
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
    kanbanSelectionIndex: number;
    jobs: Job[];
    jobRuns: JobRun[];
    meetings: Meeting[];
    meetingSelectedId: string | null;
    chatSession: SessionRecord | null;
    agentSession: SessionRecord | null;
    researchReport: ResearchRunResult | null;
    config: ConfigSnapshot | null;
    configSelectionIndex: number;
    pageFocus: Record<PageName, PageFocusTarget>;
    pageReturnFocus: Record<PageName, MainPageFocusTarget>;
    pendingAction: { type: "delete" | "archive"; ticket: Ticket } | null;
    detailTicket: Ticket | null;
    chatPending: { text: string; startedAt: number; lastRender: number } | null;
    agentPending: { text: string; startedAt: number; lastRender: number } | null;
    chatAbort: AbortController | null;
    agentAbort: AbortController | null;
  } = {
    currentPage: "Tickets",
    banner: health.status === "offline" ? { kind: "error", text: "Daemon is offline. Start it with `nina daemon start` or `make dev`." } : null,
    lastError: null,
    kanban: null,
    kanbanSelectionIndex: -1,
    jobs: [],
    jobRuns: [],
    meetings: [],
    meetingSelectedId: null,
    chatSession: null,
    agentSession: null,
    researchReport: null,
    config: null,
    configSelectionIndex: 0,
    pageFocus: { ...PAGE_DEFAULT_FOCUS },
    pageReturnFocus: { ...PAGE_DEFAULT_FOCUS },
    pendingAction: null,
    detailTicket: null,
    chatPending: null,
    agentPending: null,
    chatAbort: null,
    agentAbort: null,
  };

  const pendingTickers: Partial<Record<"chat" | "agent", ReturnType<typeof setInterval>>> = {};
  let meetingsPollTicker: ReturnType<typeof setInterval> | null = null;

  function getKanbanTickets(): { ticket: Ticket; column: string; index: number }[] {
    if (!state.kanban) return [];
    const tickets: { ticket: Ticket; column: string; index: number }[] = [];
    for (const column of orderedColumns(state.kanban)) {
      const tasks = state.kanban[column] ?? [];
      for (let i = 0; i < tasks.length; i++) {
        tickets.push({ ticket: tasks[i], column, index: i });
      }
    }
    return tickets;
  }

  function getSelectedTicket(): { ticket: Ticket; column: string } | null {
    const tickets = getKanbanTickets();
    if (state.kanbanSelectionIndex < 0 || state.kanbanSelectionIndex >= tickets.length) return null;
    const selected = tickets[state.kanbanSelectionIndex];
    return selected ? { ticket: selected.ticket, column: selected.column } : null;
  }

  let activeInput: InputRenderable | null = null;
  let configSelect: SelectRenderable | null = null;
  let activeScrollArea: ScrollBoxRenderable | null = null;
  let configInput: InputRenderable | null = null;
  let renderSequence = 0;

  function currentConfigField(): ConfigFieldDefinition {
    return CONFIG_FIELDS[Math.min(state.configSelectionIndex, CONFIG_FIELDS.length - 1)] ?? CONFIG_FIELDS[0];
  }

  function getPageFocus(page: PageName = state.currentPage): PageFocusTarget {
    return state.pageFocus[page] ?? PAGE_DEFAULT_FOCUS[page];
  }

  function getPageReturnFocus(page: PageName = state.currentPage): MainPageFocusTarget {
    return state.pageReturnFocus[page] ?? PAGE_DEFAULT_FOCUS[page];
  }

  function setPageFocus(page: PageName, target: PageFocusTarget): void {
    state.pageFocus[page] = target;
    if (target !== "tabs") {
      state.pageReturnFocus[page] = target;
    }
  }

  function focusPageTarget(page: PageName = state.currentPage): void {
    const target = getPageFocus(page);
    switch (target) {
      case "tabs":
        tabs.focus();
        return;
      case "scroll":
        if (activeScrollArea) {
          activeScrollArea.focus();
          return;
        }
        break;
      case "input":
        if (activeInput) {
          activeInput.focus();
          return;
        }
        break;
      case "select":
        if (configSelect) {
          configSelect.focus();
          return;
        }
        break;
    }

    if (page === "Config") {
      if (configInput) {
        configInput.focus();
        return;
      }
      if (configSelect) {
        configSelect.focus();
        return;
      }
    } else {
      if (activeInput) {
        activeInput.focus();
        return;
      }
      if (activeScrollArea) {
        activeScrollArea.focus();
        return;
      }
    }

    tabs.focus();
  }

  function togglePageFocus(): void {
    const page = state.currentPage;
    if (getPageFocus(page) === "tabs") {
      setPageFocus(page, getPageReturnFocus(page));
    } else {
      setPageFocus(page, "tabs");
    }
    focusPageTarget(page);
  }

  function syncConfigInputValue(): void {
    if (!state.config || !configInput) {
      return;
    }
    configInput.value = currentConfigField().getValue(state.config);
  }

  function moveConfigSelection(direction: 1 | -1): void {
    if (!state.config) {
      return;
    }
    const nextIndex = (state.configSelectionIndex + direction + CONFIG_FIELDS.length) % CONFIG_FIELDS.length;
    state.configSelectionIndex = nextIndex;
    if (configSelect) {
      configSelect.setSelectedIndex(nextIndex);
    }
    syncConfigInputValue();
  }

  async function saveConfigField(value: string): Promise<void> {
    if (!token || !state.config) {
      return;
    }
    const field = currentConfigField();
    const trimmed = value.trim();
    if (field.key === "daemon_port") {
      const parsed = Number.parseInt(trimmed, 10);
      if (Number.isNaN(parsed)) {
        state.lastError = "Daemon port must be a number.";
        renderPage("Config");
        return;
      }
    }
    state.banner = null;
    state.lastError = null;
    configInput?.blur();
    try {
      const patch = field.key === "daemon_port" ? { daemon_port: Number.parseInt(trimmed, 10) } : field.buildPatch(trimmed);
      const response = await apiFetch<ConfigUpdateResponse>(token, "/config", {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      state.config = response.config;
      state.configSelectionIndex = Math.min(state.configSelectionIndex, CONFIG_FIELDS.length - 1);
      state.banner = response.restart_required
        ? {
            kind: "info",
            text: "Config saved. Restart Nina daemon to apply host, port, or log level changes.",
          }
        : {
            kind: "success",
            text: `Config saved: ${field.label}.`,
          };
      renderPage("Config");
    } catch (error) {
      state.lastError = error instanceof Error ? error.message : String(error);
      renderPage("Config");
    }
  }


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

  function makeScrollArea(pageRoot: BoxRenderable, accent: string, title?: string): ScrollBoxRenderable {
    const page = state.currentPage;
    const scroll = new ScrollBoxRenderable(renderer, {
      flexGrow: 1,
      border: true,
      borderColor: accent,
      focusedBorderColor: THEME.text,
      backgroundColor: THEME.background,
      stickyScroll: true,
      stickyStart: "bottom",
      viewportCulling: true,
      padding: 1,
      scrollY: true,
      scrollX: false,
      title,
      titleColor: accent,
      verticalScrollbarOptions: {
        trackOptions: {
          backgroundColor: THEME.panel,
          foregroundColor: THEME.accent,
        },
        arrowOptions: {
          foregroundColor: THEME.subtle,
          backgroundColor: THEME.panel,
        },
      },
    });
    scroll.onMouseDown = () => {
      setPageFocus(page, "scroll");
      scroll.focus();
    };
    pageRoot.add(scroll);
    return scroll;
  }

  function isScrollAtBottom(scroll: ScrollBoxRenderable): boolean {
    return scroll.scrollTop + scroll.viewport.height >= scroll.scrollHeight - 2;
  }

  function scrollToBottom(scroll: ScrollBoxRenderable): void {
    scroll.scrollTo(scroll.scrollHeight);
  }

  function handleScrollKey(name: string, ctrl: boolean): void {
    const scroll = activeScrollArea;
    if (!scroll) {
      return;
    }
    setPageFocus(state.currentPage, "scroll");
    scroll.focus();
    switch (name) {
      case "home":
        if (ctrl) {
          scroll.scrollTo(0);
        } else {
          scroll.scrollBy(-scroll.scrollHeight, "absolute");
        }
        break;
      case "end":
        if (ctrl) {
          scrollToBottom(scroll);
        } else {
          scroll.scrollBy(scroll.scrollHeight, "absolute");
        }
        break;
      case "pageup":
        if (ctrl) {
          scroll.scrollBy(-scroll.scrollHeight, "absolute");
        } else {
          scroll.scrollBy(-scroll.viewport.height, "viewport");
        }
        break;
      case "pagedown":
        if (ctrl) {
          scrollToBottom(scroll);
        } else {
          scroll.scrollBy(scroll.viewport.height, "viewport");
        }
        break;
    }
  }

  function renderNewMessagesIndicator(scroll: ScrollBoxRenderable, page: PageName): void {
    if (isScrollAtBottom(scroll)) {
      return;
    }
    const indicator = new BoxRenderable(renderer, {
      border: true,
      borderColor: THEME.accent,
      backgroundColor: THEME.panelAlt,
      padding: 1,
      flexDirection: "row",
      gap: 1,
    });
    indicator.add(
      new TextRenderable(renderer, {
        content: "↓ New messages below — press Ctrl+End or End to jump to the bottom",
        fg: THEME.accent,
        wrapMode: "word",
      }),
    );
    scroll.add(indicator);
  }

  function makeInputSection(
    pageRoot: BoxRenderable,
    title: string,
    placeholder: string,
    accent: string,
  ): InputRenderable {
    const page = state.currentPage;
    const frame = new BoxRenderable(renderer, {
      border: true,
      borderColor: accent,
      focusedBorderColor: THEME.text,
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
    frame.onMouseDown = () => {
      setPageFocus(page, "input");
      input.focus();
    };
    frame.add(input);
    pageRoot.add(frame);
    return input;
  }

  function renderTicketsPage(pageRoot: BoxRenderable): void {
    const scroll = makeScrollArea(pageRoot, accentForPage("Tickets"));
    activeScrollArea = scroll;
    if (state.pendingAction) {
      const action = state.pendingAction.type === "delete" ? "Delete" : "Archive";
      const color = state.pendingAction.type === "delete" ? THEME.danger : accentForPage("Tickets");
      scroll.add(
        buildCard(
          renderer,
          `${action} ticket?`,
          color,
          `Press Y to confirm ${action.toLowerCase()} of "${state.pendingAction.ticket.title}" or N to cancel.`,
          color,
        ),
      );
    } else if (state.detailTicket) {
      const t = state.detailTicket;
      const info = [
        "Press Ctrl+E or Esc to return to the board.",
        "",
        `ID: ${t.id}`,
        `Title: ${t.title}`,
        `Description: ${t.description || "(none)"}`,
        `Status: ${t.status}`,
        `Column: ${t.kanban_column}`,
        `Position: ${t.kanban_position}`,
        `Project: ${t.project_id || "(none)"}`,
        `Note: ${t.note_path || "(none)"}`,
        `Created: ${t.created_at}`,
        `Updated: ${t.updated_at}`,
      ].join("\n");
      scroll.add(buildCard(renderer, "Task Detail", accentForPage("Tickets"), info));
    } else if (!token) {
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
      const allTickets = getKanbanTickets();
      let ticketIndex = 0;
      for (const column of orderedColumns(state.kanban)) {
        const tasks = state.kanban[column] ?? [];
        const body =
          tasks.length === 0
            ? "(empty)"
            : tasks
                .map((task) => {
                  const isSelected = ticketIndex === state.kanbanSelectionIndex;
                  ticketIndex++;
                  const description = task.description?.trim() ?? "";
                  const note = task.note_path ? `\n  note: ${task.note_path}` : "";
                  const extra = description ? `\n  ${description}` : "";
                  const prefix = isSelected ? "► " : "- ";
                  return `${prefix}${task.title} [${task.status}]${extra}${note}`;
                })
                .join("\n\n");
        scroll.add(buildCard(renderer, `${column} (${tasks.length})`, accentForPage("Tickets"), body));
      }
    }

    if (!state.detailTicket) {
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
  }

  function renderChatPage(pageRoot: BoxRenderable): void {
    const scroll = makeScrollArea(pageRoot, accentForPage("Chat"), "Chat history (scrollable)");
    activeScrollArea = scroll;
    if (!state.chatSession) {
      scroll.add(buildCard(renderer, "No session", accentForPage("Chat"), "Open the page again or send a prompt to create a chat session."));
    } else if (state.chatSession.messages.length === 0) {
      scroll.add(buildCard(renderer, "Empty chat", accentForPage("Chat"), "Send a prompt to start the conversation."));
    } else {
      for (const message of state.chatSession.messages) {
        scroll.add(renderMessageCard(message, "Chat"));
      }
    }
    if (state.chatPending) {
      scroll.add(
        buildLoadingCard(
          state.chatPending.text,
          state.chatPending.startedAt,
          `You • ${formatElapsed(Date.now() - state.chatPending.startedAt)}`,
        ),
      );
    }
    renderNewMessagesIndicator(scroll, "Chat");

    const input = makeInputSection(pageRoot, "Chat prompt", "Ask Nina a question about your vault", accentForPage("Chat"));
    activeInput = input;
    input.on(InputRenderableEvents.ENTER, (value: string) => {
      void sendChatPrompt(value, input);
    });
  }

  function renderAgentPage(pageRoot: BoxRenderable): void {
    const scroll = makeScrollArea(pageRoot, accentForPage("Agent"), "Agent history (scrollable)");
    activeScrollArea = scroll;
    if (!state.agentSession) {
      scroll.add(buildCard(renderer, "No session", accentForPage("Agent"), "Send a prompt to create an agent session."));
    } else if (state.agentSession.messages.length === 0) {
      scroll.add(buildCard(renderer, "Empty agent session", accentForPage("Agent"), "Describe a ticket or task and the agent will plan and run Nina commands."));
    } else {
      for (const message of state.agentSession.messages) {
        scroll.add(renderMessageCard(message, "Agent"));
      }
    }
    if (state.agentPending) {
      scroll.add(
        buildLoadingCard(
          state.agentPending.text,
          state.agentPending.startedAt,
          `You • ${formatElapsed(Date.now() - state.agentPending.startedAt)}`,
        ),
      );
    }
    renderNewMessagesIndicator(scroll, "Agent");

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
    activeScrollArea = scroll;
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
    activeScrollArea = scroll;
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

  function renderMeetingsPage(pageRoot: BoxRenderable): void {
    const scroll = makeScrollArea(pageRoot, accentForPage("Meetings"), "Meetings (scrollable)");
    activeScrollArea = scroll;
    if (state.meetings.length === 0) {
      scroll.add(
        buildCard(
          renderer,
          "No meetings",
          accentForPage("Meetings"),
          "Start a recording from this page or with `nina meeting record \"title\"` in a terminal. The daemon owns the audio capture; this page shows what it has tracked.",
        ),
      );
    } else {
      const selectedId = state.meetings.find(
        (m) => m.id === state.meetingSelectedId,
      )
        ? state.meetingSelectedId
        : state.meetings[0].id;
      state.meetingSelectedId = selectedId;
      for (const meeting of state.meetings) {
        const lines: string[] = [
          `Status: ${meeting.status}`,
          `Source: ${meeting.source}${meeting.device_name ? ` (${meeting.device_name})` : ""}`,
          `Started: ${formatTime(meeting.started_at)}`,
          meeting.ended_at ? `Ended: ${formatTime(meeting.ended_at)}` : "Ended: —",
          meeting.duration_seconds != null ? `Duration: ${meeting.duration_seconds}s` : "Duration: —",
          `Audio: ${meeting.audio_path}`,
        ];
        if (meeting.transcript_path) {
          lines.push(`Transcript: ${meeting.transcript_path}`);
        }
        if (meeting.summary_path) {
          lines.push(`Summary note: ${meeting.summary_path}`);
        }
        if (meeting.error) {
          lines.push(`Error: ${meeting.error}`);
        }
        const isSelected = meeting.id === state.meetingSelectedId;
        const accent = meeting.status === "recording" ? THEME.success : accentForPage("Meetings");
        const titlePrefix = isSelected ? "▶ " : "  ";
        scroll.add(
          buildCard(
            renderer,
            `${titlePrefix}${meeting.title}`,
            accent,
            lines.join("\n"),
          ),
        );
      }
    }

    const keybinds = buildCard(
      renderer,
      "Keys (all require Ctrl)",
      THEME.subtle,
      [
        "Ctrl+T transcribe    Ctrl+Y summarize    Ctrl+X stop active",
        "Ctrl+O open in Obsidian    Ctrl+P play audio    Ctrl+D delete",
        "Up/Down move the selection",
        "Type a title below and press Enter to start recording.",
      ].join("\n"),
    );
    pageRoot.add(keybinds);

    const input = makeInputSection(
      pageRoot,
      "Start a recording",
      "Type a title and press Enter to start recording. The daemon owns the audio stream, so the TUI can stay open or be closed after it starts. Press Ctrl+X here to stop.",
      accentForPage("Meetings"),
    );
    activeInput = input;
    input.on(InputRenderableEvents.ENTER, (value: string) => {
      const title = value.trim();
      if (!title) {
        return;
      }
      input.value = "";
      void startRecording(title);
    });
  }

  function renderConfigPage(pageRoot: BoxRenderable): void {
    if (!state.config) {
      pageRoot.add(
        buildCard(
          renderer,
          "No config loaded",
          accentForPage("Config"),
          "Open the page again after the daemon is reachable.",
          THEME.subtle,
        ),
      );
      return;
    }

    const config = state.config;
    const summary = [
      `Profile: ${config.profile}`,
      `Config dir: ${config.config_dir}`,
      `Config file: ${config.config_path}`,
      `Daemon health: ${health.status}`,
      `Vault path: ${config.vault_path}`,
      `Database path: ${config.database_path}`,
      `Daemon: ${config.daemon_host}:${config.daemon_port}`,
      `LLM: ${config.llm.provider} / ${config.llm.model}`,
      `Daily summary: ${config.scheduler.daily_summary_time}`,
      `Log level: ${config.log_level}`,
      "",
      "Use Up and Down to choose a setting, edit the value below, and press Enter to save.",
    ].join("\n");
    pageRoot.add(buildCard(renderer, "Current config", accentForPage("Config"), summary, THEME.text));

    const selectFrame = new BoxRenderable(renderer, {
      border: true,
      borderColor: accentForPage("Config"),
      focusedBorderColor: THEME.text,
      title: "Editable settings",
      titleColor: accentForPage("Config"),
      backgroundColor: THEME.panel,
      flexDirection: "column",
      padding: 1,
      gap: 1,
      shouldFill: true,
    });
    const select = new SelectRenderable(renderer, {
      options: CONFIG_FIELDS.map((field) => ({
        name: field.label,
        description: field.getValue(config),
        value: field.key,
      })),
      selectedIndex: Math.min(state.configSelectionIndex, CONFIG_FIELDS.length - 1),
      showDescription: true,
      showScrollIndicator: false,
      backgroundColor: THEME.panel,
      textColor: THEME.text,
      focusedBackgroundColor: THEME.panelAlt,
      focusedTextColor: THEME.text,
      selectedBackgroundColor: THEME.panelAlt,
      selectedTextColor: accentForPage("Config"),
      descriptionColor: THEME.subtle,
      selectedDescriptionColor: THEME.subtle,
    });
    configSelect = select;
    select.on(SelectRenderableEvents.SELECTION_CHANGED, (index: number) => {
      state.configSelectionIndex = Math.max(0, Math.min(index, CONFIG_FIELDS.length - 1));
      syncConfigInputValue();
    });
    selectFrame.onMouseDown = () => {
      setPageFocus("Config", "select");
      select.focus();
    };
    selectFrame.add(select);
    pageRoot.add(selectFrame);

    const currentField = currentConfigField();
    const input = makeInputSection(pageRoot, "Value", "Edit the selected setting and press Enter", accentForPage("Config"));
    configInput = input;
    input.value = currentField.getValue(config);
    input.on(InputRenderableEvents.ENTER, (value: string) => {
      void saveConfigField(value);
    });
    activeInput = input;
  }

  function renderMessageCard(message: SessionMessage, page: "Chat" | "Agent"): BoxRenderable {
    const accent = roleAccent(message.role, page);
    let body = normalizeLines(message.content);
    const metadata = message.metadata;
    if (page === "Chat" && message.role === "assistant") {
      const sources = Array.isArray(metadata.sources) ? (metadata.sources as VaultSource[]) : [];
      if (sources.length > 0) {
        body += `\n\nSources:\n${sources.map(formatSourceLine).join("\n")}`;
      }
      const toolsUsed = Array.isArray(metadata.tools_used) ? (metadata.tools_used as ToolInvocation[]) : [];
      if (toolsUsed.length > 0) {
        body += `\n\nTools used:\n${toolsUsed.map(formatToolLine).join("\n")}`;
      }
    }
    if (message.role === "tool") {
      const name = typeof metadata.name === "string" ? metadata.name : "tool";
      const summary = metadata.result_summary && typeof metadata.result_summary === "object"
        ? JSON.stringify(metadata.result_summary)
        : "";
      body = `name: ${name}\n${summary || body}`;
    }
    if (page === "Agent" && message.role === "assistant") {
      const results = Array.isArray(metadata.results) ? (metadata.results as Array<{ command: string; exit_code: number }>) : [];
      if (results.length > 0) {
        body += `\n\nExecuted ${results.length} Nina command(s).`;
      }
      const toolsUsed = Array.isArray(metadata.tools_used) ? (metadata.tools_used as ToolInvocation[]) : [];
      if (toolsUsed.length > 0) {
        body += `\n\nTools used:\n${toolsUsed.map(formatToolLine).join("\n")}`;
      }
    }
    return buildCard(renderer, roleTitle(message.role), accent, body, message.role === "tool" ? THEME.subtle : THEME.text);
  }

  function formatSourceLine(source: VaultSource): string {
    const title = source.title || source.path;
    const path = source.path || "";
    return `- ${title} (${path})`;
  }

  function formatToolLine(tool: ToolInvocation): string {
    const preview = tool.preview ? ` ${tool.preview}` : "";
    return `- ${tool.name}${preview}`;
  }

  async function createConversationSession(mode: "chat" | "agent", title: string): Promise<SessionRecord> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    return await apiFetch<SessionRecord>(token, "/sessions", {
      method: "POST",
      body: JSON.stringify({ mode, title }),
    });
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
    return await createConversationSession(mode, title);
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

  async function refreshMeetings(): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    const response = await apiFetch<{ meetings: Meeting[] }>(token, "/meetings?limit=20");
    state.meetings = response.meetings || [];
  }

  async function triggerMeetingWorkflow(meetingId: string, kind: "transcribe" | "summarize"): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    const result = await apiFetch<{ status: string; output?: { note_path?: string | null } }>(
      token,
      `/meetings/${meetingId}/${kind}`,
      { method: "POST", body: JSON.stringify({}) },
    );
    if (result.status !== "completed") {
      throw new Error(`${kind} did not complete`);
    }
    state.banner = {
      kind: "success",
      text:
        kind === "transcribe"
          ? `Transcribed ${meetingId}.`
          : `Summarized ${meetingId}.`,
    };
    if (result.output?.note_path) {
      state.banner = { ...state.banner, text: `${state.banner.text} Note: ${result.output.note_path}` };
    }
    await refreshMeetings();
    renderPage("Meetings");
  }

  async function openMeetingInObsidian(meetingId: string): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    const meeting = state.meetings.find((entry) => entry.id === meetingId);
    if (!meeting || !meeting.note_path) {
      throw new Error("Meeting has no note yet. Stop the recording first.");
    }
    await apiFetch<{ opened: boolean }>(token, "/search/open", {
      method: "POST",
      body: JSON.stringify({ path: meeting.note_path }),
    });
    state.banner = { kind: "info", text: `Requested Obsidian to open ${meeting.note_path}` };
    renderPage("Meetings");
  }

  async function playMeeting(meetingId: string): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    const meeting = state.meetings.find((entry) => entry.id === meetingId);
    if (!meeting) {
      throw new Error(`Meeting not found: ${meetingId}`);
    }
    if (!meeting.audio_path) {
      throw new Error("Meeting has no audio file.");
    }
    // If the final WAV is missing, the recorder subprocess was likely
    // killed before it could rename `.wav.partial` → `.wav`. Promote
    // the partial file in place so the meeting stays playable.
    const audioFile = meeting.audio_path;
    let playPath = audioFile;
    try {
      const exists = await Bun.file(audioFile).exists();
      if (!exists) {
        const partialPath = audioFile + ".partial";
        const partialExists = await Bun.file(partialPath).exists();
        if (partialExists) {
          await Bun.$`mv ${partialPath} ${audioFile}`.quiet();
          playPath = audioFile;
        }
      }
    } catch (err) {
      throw new Error(
        `Audio not found for meeting ${meetingId} and partial recovery failed: ${
          err instanceof Error ? err.message : String(err)
        }`
      );
    }
    if (!(await Bun.file(playPath).exists())) {
      throw new Error(`Audio not found for meeting ${meetingId}.`);
    }
    // Read the configured play command from the server. We could
    // hard-code `xdg-open` here, but the server config is the
    // single source of truth (Nina has no env-var fallback for
    // this anymore).
    const cfg = state.config;
    const playTemplate = cfg?.meetings.play_command ?? "xdg-open {path}";
    const binary = playTemplate.split(/\s+/)[0];
    if (!binary) {
      throw new Error("meetings.play_command is empty in config.");
    }
    const args = playTemplate
      .split(/\s+/)
      .slice(1)
      .map((part) => part.replace("{path}", playPath));
    // Spawn detached; we don't wait for the player to exit.
    const child = Bun.spawn([binary, ...args], {
      stdout: "ignore",
      stderr: "ignore",
    });
    child.unref();
    state.banner = {
      kind: "info",
      text: `Playing ${playPath} (${binary})`,
    };
    renderPage("Meetings");
  }

  function startMeetingsPolling(): void {
    if (meetingsPollTicker) {
      return;
    }
    meetingsPollTicker = setInterval(() => {
      // Stop polling if the user navigated away from the Meetings page
      // or if no recording is in flight.
      if (state.currentPage !== "Meetings") {
        stopMeetingsPolling();
        return;
      }
      void refreshMeetings().then(() => {
        if (!state.meetings.some((m) => m.status === "recording")) {
          stopMeetingsPolling();
        }
        if (state.currentPage === "Meetings") {
          renderPage("Meetings");
        }
      });
    }, 2000);
  }

  function stopMeetingsPolling(): void {
    if (meetingsPollTicker) {
      clearInterval(meetingsPollTicker);
      meetingsPollTicker = null;
    }
  }

  async function startRecording(title: string): Promise<void> {
    if (!token) {
      state.lastError = "No Nina token found. Run `nina init` first.";
      renderPage("Meetings");
      return;
    }
    try {
      const meeting = await apiFetch<Meeting>(token, "/meetings/record", {
        method: "POST",
        body: JSON.stringify({ title }),
      });
      state.banner = {
        kind: "info",
        text: `Recording ${meeting.id} started (${meeting.source}). Press Ctrl+X on this page to stop.`,
      };
      startMeetingsPolling();
      void refreshMeetings();
      renderPage("Meetings");
    } catch (err) {
      state.lastError = err instanceof Error ? err.message : String(err);
      renderPage("Meetings");
    }
  }

  async function deleteMeeting(meetingId: string): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    await apiFetch<{ deleted: boolean }>(token, `/meetings/${meetingId}`, { method: "DELETE" });
    state.banner = { kind: "info", text: `Deleted meeting ${meetingId}` };
    await refreshMeetings();
    renderPage("Meetings");
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
      const expanded = await expandMentions(prompt);
      startPending("chat", expanded);
      try {
        const response = await apiFetch<SessionSendResponse>(
          token,
          `/sessions/${state.chatSession.id}/messages`,
          {
            method: "POST",
            body: JSON.stringify({ content: expanded }),
            signal: state.chatAbort?.signal,
          },
        );
        state.chatSession = response.session;
      } finally {
        stopPending("chat");
      }
      renderPage("Chat");
    } catch (error) {
      if (isAbortError(error)) {
        return;
      }
      state.lastError = error instanceof Error ? error.message : String(error);
      renderPage("Chat");
    }
  }

  function startPending(kind: "chat" | "agent", text: string): void {
    // Abort any in-flight request of the same kind to avoid races.
    if (kind === "chat") {
      state.chatAbort?.abort();
      state.chatAbort = new AbortController();
    } else {
      state.agentAbort?.abort();
      state.agentAbort = new AbortController();
    }
    const now = Date.now();
    if (kind === "chat") {
      state.chatPending = { text, startedAt: now, lastRender: now };
    } else {
      state.agentPending = { text, startedAt: now, lastRender: now };
    }
    const page: PageName = kind === "chat" ? "Chat" : "Agent";
    const interval = setInterval(() => {
      const pending = kind === "chat" ? state.chatPending : state.agentPending;
      if (!pending) {
        stopPending(kind);
        return;
      }
      const last = pending.lastRender;
      const nowMs = Date.now();
      if (nowMs - last < 250) {
        return;
      }
      pending.lastRender = nowMs;
      if (state.currentPage === page) {
        renderPage(page);
      }
    }, 250);
    pendingTickers[kind] = interval;
    renderPage(page);
  }

  function stopPending(kind: "chat" | "agent"): void {
    const interval = pendingTickers[kind];
    if (interval) {
      clearInterval(interval);
      delete pendingTickers[kind];
    }
    if (kind === "chat") {
      state.chatPending = null;
      state.chatAbort = null;
    } else {
      state.agentPending = null;
      state.agentAbort = null;
    }
  }

  function isAbortError(error: unknown): boolean {
    if (!error || typeof error !== "object") {
      return false;
    }
    const name = (error as { name?: string }).name;
    return name === "AbortError" || name === "CanceledError";
  }

  function formatElapsed(ms: number): string {
    const totalSeconds = Math.max(0, Math.floor(ms / 1000));
    if (totalSeconds < 60) {
      return `${totalSeconds}s`;
    }
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
  }

  const SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

  function buildLoadingCard(
    text: string,
    startedAt: number,
    label: string,
  ): BoxRenderable {
    const elapsed = formatElapsed(Date.now() - startedAt);
    const card = new BoxRenderable(renderer, {
      border: true,
      borderColor: THEME.subtle,
      title: `${label} • ${elapsed}`,
      titleColor: THEME.subtle,
      backgroundColor: THEME.panel,
      flexDirection: "column",
      padding: 1,
      gap: 1,
    });
    card.add(
      new TextRenderable(renderer, {
        content: text,
        fg: THEME.subtle,
        wrapMode: "word",
      }),
    );
    const status = new TextRenderable(renderer, {
      content: `${SPINNER_FRAMES[Math.floor(Date.now() / 100) % SPINNER_FRAMES.length]} waiting for response…`,
      fg: THEME.accent,
      wrapMode: "word",
    });
    card.add(status);
    return card;
  }

  async function expandMentions(prompt: string): Promise<string> {
    const matches = Array.from(prompt.matchAll(/@((?:[\w./-]+\.md)|(?:[\w./-]+))/g));
    if (matches.length === 0 || !token) {
      return prompt;
    }
    const blocks: string[] = [];
    for (const match of matches) {
      const path = match[1];
      try {
        const note = await apiFetch<{ path: string; body: string; frontmatter: Record<string, unknown> }>(
          token,
          `/notes/${encodeURI(path)}`,
        );
        const title = (note.frontmatter && note.frontmatter.title) || note.path;
        const excerpt = note.body.length > 2000 ? `${note.body.slice(0, 2000)}\n...` : note.body;
        blocks.push(`Note: ${title} (${note.path})\n${excerpt}`);
      } catch (error) {
        // Surface but don't block the prompt.
        blocks.push(`Note: ${path} (failed to load: ${error instanceof Error ? error.message : String(error)})`);
      }
    }
    if (blocks.length === 0) {
      return prompt;
    }
    return `${prompt}\n\nAttached notes:\n${blocks.join("\n\n---\n\n")}`;
  }

  async function clearChatSession(): Promise<void> {
    state.banner = { kind: "info", text: "Chat cleared. Next prompt starts a new context." };
    state.lastError = null;
    state.chatSession = await createConversationSession("chat", "Chat");
    renderPage("Chat");
  }

  async function cancelCurrentSession(): Promise<void> {
    if (!token) {
      return;
    }
    const target =
      state.currentPage === "Chat"
        ? state.chatSession
        : state.currentPage === "Agent"
        ? state.agentSession
        : null;
    if (!target && !state.chatPending && !state.agentPending) {
      state.banner = { kind: "info", text: "No active session to cancel." };
      renderPage(state.currentPage);
      return;
    }
    // Abort the in-flight client request immediately.
    if (state.currentPage === "Chat") {
      state.chatAbort?.abort();
    } else if (state.currentPage === "Agent") {
      state.agentAbort?.abort();
    }
    if (target) {
      try {
        await apiFetch(token, `/sessions/${target.id}/cancel`, { method: "POST" });
        state.banner = { kind: "info", text: "Cancellation requested." };
      } catch (error) {
        if (!isAbortError(error)) {
          state.lastError = error instanceof Error ? error.message : String(error);
        }
      }
    } else {
      state.banner = { kind: "info", text: "Cancellation requested." };
    }
    renderPage(state.currentPage);
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
      startPending("agent", prompt);
      let response: SessionSendResponse | null = null;
      try {
        response = await apiFetch<SessionSendResponse>(
          token,
          `/sessions/${state.agentSession.id}/messages`,
          {
            method: "POST",
            body: JSON.stringify({ content: prompt }),
            signal: state.agentAbort?.signal,
          },
        );
      } finally {
        stopPending("agent");
      }
      if (response) {
        state.agentSession = response.session;
        state.banner = { kind: "success", text: response.assistant.content };
      }
      renderPage("Agent");
    } catch (error) {
      if (isAbortError(error)) {
        renderPage("Agent");
        return;
      }
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
    activeInput = null;
    activeScrollArea = null;
    configSelect = null;
    configInput = null;

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
      case "Meetings":
        renderMeetingsPage(pageRoot);
        break;
      case "Jobs":
        renderJobsPage(pageRoot);
        break;
      case "Config":
        renderConfigPage(pageRoot);
        break;
    }

    clearChildren(content);
    content.add(pageRoot);
    focusPageTarget(page);
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
      case "Meetings":
        await refreshMeetings();
        break;
      case "Jobs":
        await refreshJobs();
        break;
      case "Config":
        state.config = await apiFetch<ConfigSnapshot>(token, "/config");
        state.configSelectionIndex = Math.min(state.configSelectionIndex, CONFIG_FIELDS.length - 1);
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

  renderer.keyInput.on("keypress", (key: KeyEvent) => {
    if ((key.name === "tab" || key.name === "backtab") && !key.ctrl && !key.meta && !key.option && !key.super) {
      moveTabSelection(tabs, key.shift || key.name === "backtab" ? -1 : 1);
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.currentPage === "Config" && configSelect && (key.name === "up" || key.name === "down") && !key.ctrl && !key.meta && !key.option && !key.super) {
      moveConfigSelection(key.name === "up" ? -1 : 1);
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (key.name === "f6" && !key.ctrl && !key.meta && !key.option && !key.super) {
      togglePageFocus();
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (key.name === "escape" || key.name === "esc") {
      if (activeInput) {
        activeInput.blur();
      }
      setPageFocus(state.currentPage, "tabs");
      tabs.focus();
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (key.ctrl && key.name === "q" && state.currentPage === "Chat") {
      void clearChatSession();
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (key.ctrl && key.name === ".") {
      void cancelCurrentSession();
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (key.ctrl && key.name === "r") {
      void switchPage(state.currentPage);
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.currentPage === "Meetings" && key.ctrl) {
      const currentIndex = state.meetings.findIndex(
        (m) => m.id === state.meetingSelectedId,
      );
      const selected = currentIndex >= 0
        ? state.meetings[currentIndex]
        : state.meetings[0];

      // Up/Down still work without Ctrl (they don't conflict with the
      // text input because they're navigation keys, not letters).
      if (key.name === "up" || key.name === "down") {
        if (state.meetings.length > 0) {
          const baseIndex = currentIndex >= 0 ? currentIndex : 0;
          const delta = key.name === "down" ? 1 : -1;
          const nextIndex =
            (baseIndex + delta + state.meetings.length) % state.meetings.length;
          state.meetingSelectedId = state.meetings[nextIndex].id;
          renderPage("Meetings");
        }
        key.preventDefault();
        key.stopPropagation();
        return;
      }

      // Every action below requires Ctrl so the text input on this page
      // doesn't swallow the keystrokes. Pick letters that don't collide
      // with terminal-reserved combos (Ctrl+C, Ctrl+M, Ctrl+S, Ctrl+Z
      // are commonly intercepted by the line discipline).
      if (key.name === "x") {
        // Ctrl+X — stop the active recording
        void (async () => {
          try {
            const recording = state.meetings.find((m) => m.status === "recording");
            if (recording) {
              await apiFetch(token, `/meetings/${recording.id}/stop`, {
                method: "POST",
                body: JSON.stringify({}),
              });
              state.banner = { kind: "info", text: `Stopped meeting ${recording.id}.` };
            } else {
              state.banner = { kind: "info", text: "No active recording to stop." };
            }
            await refreshMeetings();
            renderPage("Meetings");
          } catch (error) {
            state.lastError = error instanceof Error ? error.message : String(error);
            renderPage("Meetings");
          }
        })();
        key.preventDefault();
        key.stopPropagation();
        return;
      }
      if (key.name === "t" && selected) {
        // Ctrl+T — transcribe
        void triggerMeetingWorkflow(selected.id, "transcribe").catch((err: unknown) => {
          state.lastError = err instanceof Error ? err.message : String(err);
          renderPage("Meetings");
        });
        key.preventDefault();
        key.stopPropagation();
        return;
      }
      if (key.name === "y" && selected) {
        // Ctrl+Y — summarize (Y for summarYze, avoids Ctrl+M = Enter)
        void triggerMeetingWorkflow(selected.id, "summarize").catch((err: unknown) => {
          state.lastError = err instanceof Error ? err.message : String(err);
          renderPage("Meetings");
        });
        key.preventDefault();
        key.stopPropagation();
        return;
      }
      if (key.name === "o" && selected) {
        // Ctrl+O — open in Obsidian
        void openMeetingInObsidian(selected.id).catch((err: unknown) => {
          state.lastError = err instanceof Error ? err.message : String(err);
          renderPage("Meetings");
        });
        key.preventDefault();
        key.stopPropagation();
        return;
      }
      if (key.name === "p" && selected) {
        // Ctrl+P — play
        void playMeeting(selected.id).catch((err: unknown) => {
          state.lastError = err instanceof Error ? err.message : String(err);
          renderPage("Meetings");
        });
        key.preventDefault();
        key.stopPropagation();
        return;
      }
      if (key.name === "d" && selected) {
        // Ctrl+D — delete
        void deleteMeeting(selected.id).catch((err: unknown) => {
          state.lastError = err instanceof Error ? err.message : String(err);
          renderPage("Meetings");
        });
        key.preventDefault();
        key.stopPropagation();
        return;
      }
    }
    if (key.name === "pageup" || key.name === "pagedown" || key.name === "home" || key.name === "end") {
      handleScrollKey(key.name, key.ctrl);
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (
      key.ctrl &&
      (key.name === "up" || key.name === "down") &&
      state.currentPage !== "Tickets"
    ) {
      const delta = key.name === "up" ? -1 : 1;
      handleScrollKey("pagedown", false);
      const scroll = activeScrollArea;
      if (scroll) {
        const lineDelta = delta * 3;
        scroll.scrollBy(lineDelta, "absolute");
      }
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.currentPage === "Tickets" && key.ctrl && (key.name === "up" || key.name === "down")) {
      const tickets = getKanbanTickets();
      if (tickets.length === 0) return;
      const direction = key.name === "up" ? -1 : 1;
      if (state.kanbanSelectionIndex === -1) {
        state.kanbanSelectionIndex = direction > 0 ? 0 : tickets.length - 1;
      } else {
        state.kanbanSelectionIndex = (state.kanbanSelectionIndex + direction + tickets.length) % tickets.length;
      }
      renderPage("Tickets");
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.currentPage === "Tickets" && key.ctrl && (key.name === "right" || key.name === "left")) {
      const selected = getSelectedTicket();
      if (!selected) {
        const tickets = getKanbanTickets();
        if (tickets.length > 0) {
          state.kanbanSelectionIndex = 0;
          key.preventDefault();
          key.stopPropagation();
          return;
        }
      } else {
        const columns = orderedColumns(state.kanban ?? {});
        const currentIndex = columns.indexOf(selected.column);
        const nextIndex = key.name === "right"
          ? Math.min(currentIndex + 1, columns.length - 1)
          : Math.max(currentIndex - 1, 0);
        const nextColumn = columns[nextIndex];
        if (nextColumn !== selected.column) {
          void (async () => {
            try {
              await apiFetch(token, "/kanban/move", {
                method: "POST",
                body: JSON.stringify({
                  task_id: selected.ticket.id,
                  to_column: nextColumn,
                  to_position: 0,
                }),
              });
              state.banner = { kind: "success", text: `Moved ${selected.ticket.title} to ${nextColumn}` };
              await refreshTickets();
              renderPage("Tickets");
            } catch (error) {
              state.lastError = error instanceof Error ? error.message : String(error);
              renderPage("Tickets");
            }
          })();
        }
      }
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.pendingAction && (key.name === "y" || key.name === "Y")) {
      const { type, ticket } = state.pendingAction;
      state.pendingAction = null;
      void (async () => {
        try {
          const endpoint = type === "delete" ? `/tickets/${ticket.id}` : `/tasks/${ticket.id}/archive`;
          const method = type === "delete" ? "DELETE" : "POST";
          await apiFetch(token, endpoint, { method });
          state.banner = { kind: "success", text: `${type === "delete" ? "Deleted" : "Archived"} ticket ${ticket.id}` };
          state.kanbanSelectionIndex = -1;
          await refreshTickets();
          renderPage("Tickets");
        } catch (error) {
          state.lastError = error instanceof Error ? error.message : String(error);
          renderPage("Tickets");
        }
      })();
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.pendingAction && (key.name === "n" || key.name === "N" || key.name === "escape" || key.name === "esc")) {
      state.pendingAction = null;
      renderPage("Tickets");
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.currentPage === "Tickets" && key.ctrl && key.name === "d") {
      const selected = getSelectedTicket();
      if (selected) {
        state.pendingAction = { type: "delete", ticket: selected.ticket };
        renderPage("Tickets");
      }
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.currentPage === "Tickets" && key.ctrl && key.name === "a") {
      const selected = getSelectedTicket();
      if (selected) {
        state.pendingAction = { type: "archive", ticket: selected.ticket };
        renderPage("Tickets");
      }
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.currentPage === "Tickets" && state.detailTicket && (key.name === "escape" || key.name === "esc")) {
      state.detailTicket = null;
      renderPage("Tickets");
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.currentPage === "Tickets" && key.ctrl && key.name === "e") {
      if (state.detailTicket) {
        state.detailTicket = null;
        renderPage("Tickets");
      } else {
        const selected = getSelectedTicket();
        if (selected) {
          state.detailTicket = selected.ticket;
          renderPage("Tickets");
        }
      }
      key.preventDefault();
      key.stopPropagation();
      return;
    }
  });

    await switchPage(state.currentPage);
}

main().catch((err) => {
  console.error("TUI error:", err);
  process.exit(1);
});
