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
import { spawn } from "child_process";
import { readFileSync } from "fs";
import { homedir } from "os";
import { join } from "path";
import { consumeKey, ctrlDigitIndex, ctrlLineScrollDirection, globalShortcutHelp, isCtrlKey, isCtrlSpace, scrollPageKey, tabDirection } from "./keymap";
import { THEME } from "../ui/theme";

import type {
  Ticket,
  TaskGroup,
  CodexTaskLogsResponse,
  Repository,
  RepositoryWorktree,
  Job,
  JobRun,
  WorkflowInfo,
  MessageMetadata,
  SessionMessage,
  SessionRecord,
  SessionSendResponse,
  VaultSource,
  ToolInvocation,
  ResearchRunResult,
  HealthResponse,
  RuntimeState,
  ConfigSnapshot,
  Meeting,
  IntegrationIdentity,
  IntegrationTestSummary,
  IntegrationRecord,
  IntegrationsResponse,
  ConfigUpdateResponse,
  ConfigFieldKey,
  ConfigFieldDefinition,
  Banner,
  PageName,
  PageFocusTarget,
  MainPageFocusTarget
} from "../api/types";

import { PAGE_ACCENTS, PAGE_DEFAULT_FOCUS, PAGE_DESCRIPTIONS, PAGE_HELP, PAGE_INTRO, PAGE_NAMES } from "./pages";

const TASK_TYPE_ORDER = [
  "unclassified",
  "coding",
  "reviewing",
  "research",
  "reminder",
  "blocked",
  "done",
];

const TASK_TYPE_HOTKEY_HELP = "Ctrl+1..7 types: 1=unclassified, 2=coding, 3=reviewing, 4=research, 5=reminder, 6=blocked, 7=done";
const TASK_TYPES_WITHOUT_REPOSITORY = new Set(["unclassified", "research", "reminder", "blocked", "done"]);

type TaskDraft = {
  taskType: string;
  repositoryId: string | null;
  autoRun: boolean;
};

type TaskCreateField = "title" | "description" | "taskType" | "repository" | "autoRun";

type TaskCreateModalState = {
  open: boolean;
  activeFieldIndex: number;
  title: string;
  description: string;
  taskType: string;
  repositoryId: string | null;
  autoRun: boolean;
  error: string | null;
  submitting: boolean;
};

type TaskLogModalState = {
  open: boolean;
  ticket: Ticket | null;
  data: CodexTaskLogsResponse | null;
  loading: boolean;
  error: string | null;
  notice: string | null;
  scrollOffset: number;
};

const TASK_CREATE_FIELDS: TaskCreateField[] = ["title", "description", "taskType", "repository", "autoRun"];

function emptyTaskCreateModal(): TaskCreateModalState {
  return {
    open: false,
    activeFieldIndex: 0,
    title: "",
    description: "",
    taskType: "unclassified",
    repositoryId: null,
    autoRun: true,
    error: null,
    submitting: false,
  };
}

function emptyTaskLogModal(): TaskLogModalState {
  return {
    open: false,
    ticket: null,
    data: null,
    loading: false,
    error: null,
    notice: null,
    scrollOffset: 0,
  };
}

function taskTypeRequiresRepository(taskType: string): boolean {
  return !TASK_TYPES_WITHOUT_REPOSITORY.has(taskType);
}

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
  if (envDir) return envDir;
  const profile = process.env.NINA_PROFILE || "default";
  return join(homedir(), ".nina", profile);
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

type ClipboardCommand = { command: string; args: string[] };

function clipboardCommands(): ClipboardCommand[] {
  if (process.platform === "darwin") {
    return [{ command: "pbcopy", args: [] }];
  }
  if (process.platform === "win32") {
    return [{ command: "cmd.exe", args: ["/c", "clip"] }];
  }
  return [
    { command: "wl-copy", args: [] },
    { command: "xclip", args: ["-selection", "clipboard"] },
    { command: "xsel", args: ["--clipboard", "--input"] },
  ];
}

function writeClipboard(command: ClipboardCommand, text: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(command.command, command.args, { stdio: ["pipe", "ignore", "pipe"] });
    let stderr = "";
    let settled = false;
    const fail = (error: unknown) => {
      if (settled) {
        return;
      }
      settled = true;
      reject(error instanceof Error ? error : new Error(String(error)));
    };
    child.on("error", fail);
    child.stderr?.on("data", (chunk) => {
      stderr += String(chunk);
    });
    child.on("close", (code) => {
      if (settled) {
        return;
      }
      settled = true;
      if (code === 0) {
        resolve();
      } else {
        const detail = stderr.trim();
        reject(new Error(`${command.command} exited with ${code}${detail ? `: ${detail}` : ""}`));
      }
    });
    if (!child.stdin) {
      fail(new Error(`${command.command} did not open stdin`));
      return;
    }
    child.stdin.on("error", fail);
    child.stdin.end(text);
  });
}

async function copyTextToClipboard(text: string): Promise<void> {
  const failures: string[] = [];
  for (const command of clipboardCommands()) {
    try {
      await writeClipboard(command, text);
      return;
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      failures.push(`${command.command}: ${detail}`);
    }
  }
  const installHint = process.platform === "linux" ? " Install wl-copy, xclip, or xsel." : "";
  throw new Error(`Could not copy to clipboard.${installHint} ${failures.join("; ")}`.trim());
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

function parseRepositoryDraft(value: string): { path: string; name: string } {
  const trimmed = value.trim();
  const parts = trimmed.split(" | ");
  return {
    path: (parts[0] ?? "").trim(),
    name: (parts[1] ?? "").trim(),
  };
}

function formatTime(value: string | null): string {
  return value && value.length > 0 ? value : "never";
}

function orderedTaskTypes(group: TaskGroup): string[] {
  const seen = new Set<string>();
  const types: string[] = [];
  for (const name of TASK_TYPE_ORDER) {
    if (group[name]) {
      types.push(name);
      seen.add(name);
    }
  }
  for (const name of Object.keys(group).sort()) {
    if (!seen.has(name)) {
      types.push(name);
    }
  }
  return types;
}

function taskTypeAccent(type: string): string {
  switch (type) {
    case "coding":
      return "#22c55e";
    case "reviewing":
      return "#38bdf8";
    case "research":
      return "#eab308";
    case "reminder":
      return "#f97316";
    case "blocked":
      return "#94a3b8";
    case "done":
      return "#22d3ee";
    case "unclassified":
      return "#a855f7";
    default:
      return "#60a5fa";
  }
}

function taskAutomationStatus(task: Ticket): string {
  const lines = ["Status: " + task.status, "Logs: Ctrl+L opens the latest Codex run log. Refresh with Ctrl+R."];
  if (task.status === "working") {
    lines.unshift("Codex is currently working on this task.");
  } else if (task.status === "error") {
    lines.unshift("The last automation run ended with an error.");
  } else {
    lines.unshift("No Codex run is active right now.");
  }
  return lines.join("\n");
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
    key: "research.provider",
    label: "Research provider",
    description: "Research backend",
    restartRequired: false,
    getValue: (config) => config.research.provider,
    buildPatch: (value) => ({ research: { provider: value } }),
  },
  {
    key: "research.model",
    label: "Research model",
    description: "Codex model or codex-cli",
    restartRequired: false,
    getValue: (config) => config.research.model,
    buildPatch: (value) => ({ research: { model: value } }),
  },
  {
    key: "research.search_mode",
    label: "Research search",
    description: "live | cached | disabled",
    restartRequired: false,
    getValue: (config) => config.research.search_mode,
    buildPatch: (value) => ({ research: { search_mode: value } }),
  },
  {
    key: "research.timeout_seconds",
    label: "Research timeout",
    description: "Codex research timeout in seconds",
    restartRequired: false,
    getValue: (config) => String(config.research.timeout_seconds),
    buildPatch: (value) => ({ research: { timeout_seconds: Number.parseFloat(value) } }),
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

export async function runTui(): Promise<void> {
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
    useMouse: false,
    enableMouseMovement: false,
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
    tasks: TaskGroup | null;
    tasksSelectionIndex: number;
    taskDraft: TaskDraft;
    taskCreateModal: TaskCreateModalState;
    taskLogModal: TaskLogModalState;
    repositories: Repository[];
    repositoryWorktrees: Record<string, RepositoryWorktree[]>;
    repositoryWorktreeErrors: Record<string, string>;
    repositoriesSelectionIndex: number;
    jobs: Job[];
    workflows: Record<string, string>;
    jobsView: "list" | "detail";
    jobsSelectionIndex: number;
    jobsDetailJobName: string | null;
    jobsDetailRuns: JobRun[];
    meetings: Meeting[];
    meetingSelectedId: string | null;
    chatSession: SessionRecord | null;
    agentSession: SessionRecord | null;
    researchReport: ResearchRunResult | null;
    config: ConfigSnapshot | null;
    configSelectionIndex: number;
    integrations: IntegrationRecord[];
    pageFocus: Record<PageName, PageFocusTarget>;
    pageReturnFocus: Record<PageName, MainPageFocusTarget>;
    pendingAction: { type: "delete" | "archive"; ticket: Ticket } | null;
    detailTicket: Ticket | null;
    chatPending: { text: string; startedAt: number } | null;
    agentPending: { text: string; startedAt: number } | null;
    researchPending: { text: string; startedAt: number } | null;
    chatAbort: AbortController | null;
    agentAbort: AbortController | null;
  } = {
    currentPage: "Tickets",
    banner: health.status === "offline" ? { kind: "error", text: "Daemon is offline. Start it with `nina daemon start` or `make dev`." } : null,
    lastError: null,
    tasks: null,
    tasksSelectionIndex: -1,
    taskDraft: { taskType: "unclassified", repositoryId: null, autoRun: true },
    taskCreateModal: emptyTaskCreateModal(),
    taskLogModal: emptyTaskLogModal(),
    repositories: [],
    repositoryWorktrees: {},
    repositoryWorktreeErrors: {},
    repositoriesSelectionIndex: -1,
    jobs: [],
    workflows: {},
    jobsView: "list",
    jobsSelectionIndex: 0,
    jobsDetailJobName: null,
    jobsDetailRuns: [],
    meetings: [],
    meetingSelectedId: null,
    chatSession: null,
    agentSession: null,
    researchReport: null,
    config: null,
    configSelectionIndex: 0,
    integrations: [],
    pageFocus: { ...PAGE_DEFAULT_FOCUS },
    pageReturnFocus: { ...PAGE_DEFAULT_FOCUS },
    pendingAction: null,
    detailTicket: null,
    chatPending: null,
    agentPending: null,
    researchPending: null,
    chatAbort: null,
    agentAbort: null,
  };


  function getVisibleTasks(): { ticket: Ticket; taskType: string; index: number }[] {
    if (!state.tasks) return [];
    const out: { ticket: Ticket; taskType: string; index: number }[] = [];
    for (const taskType of orderedTaskTypes(state.tasks)) {
      const tasks = state.tasks[taskType] ?? [];
      for (let i = 0; i < tasks.length; i++) {
        out.push({ ticket: tasks[i], taskType, index: i });
      }
    }
    return out;
  }

  function getSelectedTask(): { ticket: Ticket; taskType: string } | null {
    const tasks = getVisibleTasks();
    if (state.tasksSelectionIndex < 0 || state.tasksSelectionIndex >= tasks.length) return null;
    const selected = tasks[state.tasksSelectionIndex];
    return selected ? { ticket: selected.ticket, taskType: selected.taskType } : null;
  }

  function findTaskById(taskId: string): Ticket | null {
    if (!state.tasks) return null;
    for (const tasks of Object.values(state.tasks)) {
      const found = tasks.find((task) => task.id === taskId);
      if (found) return found;
    }
    return null;
  }

  function repositoryById(repositoryId: string | null): Repository | null {
    if (!repositoryId) return null;
    return state.repositories.find((repo) => repo.id === repositoryId) ?? null;
  }

  function repositoryLabel(repositoryId: string | null): string {
    const repo = repositoryById(repositoryId);
    if (!repo) return "(none)";
    return `${repo.name} (${repo.path})`;
  }

  function ticketRepositoryLabel(task: Ticket): string {
    if (task.repository_name || task.repository_path) {
      return `${task.repository_name || task.repository_id || "repository"}${task.repository_path ? ` (${task.repository_path})` : ""}`;
    }
    return "(none)";
  }

  function repositoryWorktreeLines(repo: Repository): string {
    const error = state.repositoryWorktreeErrors[repo.id];
    if (error) {
      return `  worktrees: unavailable - ${error}`;
    }
    const worktrees = state.repositoryWorktrees[repo.id] ?? [];
    if (worktrees.length === 0) {
      return "  worktrees: (none reported)";
    }
    const rows = worktrees.map((worktree) => {
      const label = worktree.branch || (worktree.detached ? "detached" : worktree.bare ? "bare" : "unknown");
      const head = worktree.head ? worktree.head.slice(0, 7) : "no-head";
      const flags = [
        label,
        head,
        worktree.locked ? "locked" : null,
        worktree.prunable ? "prunable" : null,
      ].filter(Boolean).join(", ");
      return `    - ${worktree.path} [${flags}]`;
    });
    return ["  worktrees:", ...rows].join("\n");
  }

  function normalizeTaskDraftRepository(): void {
    if (state.repositories.length === 0) {
      state.taskDraft.repositoryId = null;
      return;
    }
    if (state.taskDraft.repositoryId && repositoryById(state.taskDraft.repositoryId)) {
      return;
    }
    state.taskDraft.repositoryId = state.repositories[0]?.id ?? null;
  }

  let activeInput: InputRenderable | null = null;
  let configSelect: SelectRenderable | null = null;
  let activeScrollArea: ScrollBoxRenderable | null = null;
  let configInput: InputRenderable | null = null;
  let renderSequence = 0;

  function currentTaskCreateField(): TaskCreateField {
    return TASK_CREATE_FIELDS[Math.min(state.taskCreateModal.activeFieldIndex, TASK_CREATE_FIELDS.length - 1)] ?? "title";
  }

  function setTaskCreateActiveField(field: TaskCreateField): void {
    const index = TASK_CREATE_FIELDS.indexOf(field);
    if (index >= 0) {
      state.taskCreateModal.activeFieldIndex = index;
    }
  }

  function taskCreateRepositoryChoices(): (string | null)[] {
    const repoIds = state.repositories.map((repo) => repo.id);
    return taskTypeRequiresRepository(state.taskCreateModal.taskType) ? repoIds : [null, ...repoIds];
  }

  function normalizeTaskCreateRepository(): void {
    const modal = state.taskCreateModal;
    if (!modal.open) {
      return;
    }
    const choices = taskCreateRepositoryChoices();
    if (choices.length === 0) {
      modal.repositoryId = null;
      return;
    }
    if (!choices.includes(modal.repositoryId)) {
      modal.repositoryId = choices[0] ?? null;
    }
  }

  function openTaskCreateModal(): void {
    state.taskCreateModal = {
      ...emptyTaskCreateModal(),
      open: true,
      taskType: state.taskDraft.taskType,
      repositoryId: state.taskDraft.repositoryId,
      autoRun: state.taskDraft.autoRun,
    };
    normalizeTaskCreateRepository();
    setPageFocus("Tickets", "input");
    renderPage("Tickets");
  }

  function closeTaskCreateModal(): void {
    state.taskCreateModal = emptyTaskCreateModal();
    setPageFocus("Tickets", "scroll");
    renderPage("Tickets");
  }

  function moveTaskCreateField(direction: 1 | -1): void {
    const count = TASK_CREATE_FIELDS.length;
    state.taskCreateModal.activeFieldIndex = (state.taskCreateModal.activeFieldIndex + direction + count) % count;
    const field = currentTaskCreateField();
    setPageFocus("Tickets", field === "title" || field === "description" ? "input" : "scroll");
    state.taskCreateModal.error = null;
    renderPage("Tickets");
  }

  function cycleTaskCreateOption(direction: 1 | -1): boolean {
    const modal = state.taskCreateModal;
    const field = currentTaskCreateField();
    if (field === "taskType") {
      const idx = TASK_TYPE_ORDER.indexOf(modal.taskType);
      const baseIndex = idx >= 0 ? idx : 0;
      modal.taskType = TASK_TYPE_ORDER[(baseIndex + direction + TASK_TYPE_ORDER.length) % TASK_TYPE_ORDER.length];
      modal.error = null;
      normalizeTaskCreateRepository();
      renderPage("Tickets");
      return true;
    }
    if (field === "repository") {
      const choices = taskCreateRepositoryChoices();
      if (choices.length === 0) {
        modal.repositoryId = null;
        modal.error = "Register a repository first.";
        renderPage("Tickets");
        return true;
      }
      const idx = choices.indexOf(modal.repositoryId);
      const baseIndex = idx >= 0 ? idx : 0;
      modal.repositoryId = choices[(baseIndex + direction + choices.length) % choices.length] ?? null;
      modal.error = null;
      renderPage("Tickets");
      return true;
    }
    if (field === "autoRun") {
      modal.autoRun = !modal.autoRun;
      modal.error = null;
      renderPage("Tickets");
      return true;
    }
    return false;
  }

  async function submitTaskCreateModal(): Promise<void> {
    const modal = state.taskCreateModal;
    if (!modal.open || modal.submitting) {
      return;
    }
    if (!token) {
      modal.error = "Run nina init first so the TUI can talk to the daemon.";
      renderPage("Tickets");
      return;
    }
    const title = modal.title.trim();
    const description = modal.description.trim();
    if (!title) {
      modal.error = "Title is required.";
      setTaskCreateActiveField("title");
      renderPage("Tickets");
      return;
    }
    if (taskTypeRequiresRepository(modal.taskType) && !modal.repositoryId) {
      modal.error = "This task type requires a registered repository.";
      setTaskCreateActiveField("repository");
      renderPage("Tickets");
      return;
    }
    modal.error = null;
    modal.submitting = true;
    state.banner = null;
    state.lastError = null;
    renderPage("Tickets");
    try {
      const created = await apiFetch<Ticket>(token, "/tasks", {
        method: "POST",
        body: JSON.stringify({
          title,
          description,
          repository_id: modal.repositoryId,
          task_type: modal.taskType,
          auto_run: modal.autoRun,
          auto_run_background: modal.autoRun,
        }),
      });
      state.taskDraft = {
        taskType: modal.taskType,
        repositoryId: modal.repositoryId,
        autoRun: modal.autoRun,
      };
      state.taskCreateModal = emptyTaskCreateModal();
      state.detailTicket = null;
      state.banner = {
        kind: "success",
        text: modal.autoRun
          ? `Created task ${created.id} and queued Nina/Codex.`
          : `Created task ${created.id}.`,
      };
      await refreshTasks();
      const createdIndex = getVisibleTasks().findIndex((task) => task.ticket.id === created.id);
      state.tasksSelectionIndex = createdIndex >= 0 ? createdIndex : 0;
      renderPage("Tickets");
    } catch (error) {
      modal.submitting = false;
      modal.error = error instanceof Error ? error.message : String(error);
      state.lastError = modal.error;
      renderPage("Tickets");
    }
  }

  function handleTaskCreateModalKey(key: KeyEvent): boolean {
    if (!state.taskCreateModal.open) {
      return false;
    }
    const ctrlOnly = Boolean(key.ctrl && !key.meta && !key.option && !key.super);
    const commandModified = Boolean(key.ctrl || key.meta || key.option || key.super);
    if (key.name === "escape" || key.name === "esc") {
      closeTaskCreateModal();
      consumeKey(key);
      return true;
    }
    if (ctrlOnly && (key.name === "up" || key.name === "down")) {
      moveTaskCreateField(key.name === "up" ? -1 : 1);
      consumeKey(key);
      return true;
    }
    if (ctrlOnly && (key.name === "left" || key.name === "right")) {
      cycleTaskCreateOption(key.name === "left" ? -1 : 1);
      consumeKey(key);
      return true;
    }
    if (key.name === "return" || key.name === "enter" || key.name === "kpenter") {
      void submitTaskCreateModal();
      consumeKey(key);
      return true;
    }
    if (commandModified) {
      consumeKey(key);
      return true;
    }
    const field = currentTaskCreateField();
    if (field === "title" || field === "description") {
      return false;
    }
    consumeKey(key);
    return true;
  }

  async function fetchTaskLogs(taskId: string, runId: string | null = null, tail = 200): Promise<CodexTaskLogsResponse> {
    const params = new URLSearchParams({ tail: String(tail) });
    if (runId) {
      params.set("run_id", runId);
    }
    return await apiFetch<CodexTaskLogsResponse>(
      token,
      `/tasks/${encodeURIComponent(taskId)}/codex-logs?${params.toString()}`,
    );
  }

  function closeTaskLogModal(): void {
    state.taskLogModal = emptyTaskLogModal();
    setPageFocus("Tickets", "scroll");
    renderPage("Tickets");
  }

  async function refreshTaskLogModal(): Promise<void> {
    const modal = state.taskLogModal;
    const ticket = modal.ticket;
    if (!modal.open || !ticket) {
      return;
    }
    modal.loading = true;
    modal.error = null;
    renderPage("Tickets");
    try {
      const data = await fetchTaskLogs(ticket.id, modal.data?.run_id ?? null);
      if (state.taskLogModal.open && state.taskLogModal.ticket?.id === ticket.id) {
        state.taskLogModal.data = data;
        state.taskLogModal.loading = false;
        state.taskLogModal.error = null;
        renderPage("Tickets");
      }
    } catch (error) {
      if (state.taskLogModal.open && state.taskLogModal.ticket?.id === ticket.id) {
        state.taskLogModal.loading = false;
        state.taskLogModal.error = error instanceof Error ? error.message : String(error);
        renderPage("Tickets");
      }
    }
  }

  function formatTaskLogClipboard(ticket: Ticket | null, data: CodexTaskLogsResponse): string {
    return [
      ticket ? `Task: ${ticket.title}` : `Task: ${data.task_id}`,
      `Task ID: ${data.task_id}`,
      `Run: ${data.run_id ?? "(none)"}`,
      `Path: ${data.path}`,
      "",
      ...data.lines,
    ].join("\n");
  }

  async function copyTaskLogModalToClipboard(): Promise<void> {
    const modal = state.taskLogModal;
    const ticket = modal.ticket;
    if (!modal.open || !ticket) {
      return;
    }
    modal.error = null;
    modal.notice = "Copying full log...";
    renderPage("Tickets");
    try {
      const data = await fetchTaskLogs(ticket.id, modal.data?.run_id ?? null, -1);
      const text = formatTaskLogClipboard(ticket, data);
      await copyTextToClipboard(text);
      if (state.taskLogModal.open && state.taskLogModal.ticket?.id === ticket.id) {
        state.taskLogModal.notice = `Copied ${data.lines.length} log lines to clipboard.`;
        state.taskLogModal.error = null;
        renderPage("Tickets");
      }
    } catch (error) {
      if (state.taskLogModal.open && state.taskLogModal.ticket?.id === ticket.id) {
        state.taskLogModal.notice = null;
        state.taskLogModal.error = error instanceof Error ? error.message : String(error);
        renderPage("Tickets");
      }
    }
  }

  function openTaskLogModal(ticket: Ticket): void {

    state.taskCreateModal = emptyTaskCreateModal();
    state.taskLogModal = {
      ...emptyTaskLogModal(),
      open: true,
      ticket,
      loading: true,
    };
    setPageFocus("Tickets", "scroll");
    renderPage("Tickets");
    void refreshTaskLogModal();
  }

  function handleTaskLogModalKey(key: KeyEvent): boolean {
    if (!state.taskLogModal.open) {
      return false;
    }
    const ctrlOnly = Boolean(key.ctrl && !key.meta && !key.option && !key.super);
    if (key.name === "escape" || key.name === "esc") {
      closeTaskLogModal();
      consumeKey(key);
      return true;
    }
    if (ctrlOnly && key.name === "r") {
      void refreshTaskLogModal();
      consumeKey(key);
      return true;
    }
    if (ctrlOnly && key.name === "p") {
      void copyTaskLogModalToClipboard();
      consumeKey(key);
      return true;
    }
    if (isTaskLogScrollKey(key)) {
      const scroll = activeScrollArea;
      if (scroll) {
        scroll.focus();
        scroll.handleKeyPress(key);
        state.taskLogModal.scrollOffset = scroll.scrollTop;
      }
      consumeKey(key);
      return true;
    }
    consumeKey(key);
    return true;
  }

  function isTaskLogScrollKey(key: KeyEvent): boolean {
    if (key.meta || key.option || key.super) {
      return false;
    }
    return ["up", "down", "pageup", "pagedown", "home", "end", "j", "k"].includes(key.name ?? "");
  }

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
    scroll.onMouseScroll = (event: TuiMouseEvent) => {
      setPageFocus(page, "scroll");
      scroll.focus();
      const amount = Math.max(1, event.scroll?.delta ?? 1) * 3;
      if (event.scroll?.direction === "up") {
        scroll.scrollBy(-amount, "absolute");
      } else if (event.scroll?.direction === "down") {
        scroll.scrollBy(amount, "absolute");
      }
      event.preventDefault();
      event.stopPropagation();
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

  function handleScrollKey(name: string, ctrl: boolean): boolean {
    const scroll = activeScrollArea;
    if (!scroll) {
      return false;
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
    return true;
  }

  function handleLineScroll(direction: -1 | 1): boolean {
    const scroll = activeScrollArea;
    if (!scroll) {
      return false;
    }
    setPageFocus(state.currentPage, "scroll");
    scroll.focus();
    scroll.scrollBy(direction * 3, "absolute");
    return true;
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

  function renderTaskCreateModal(pageRoot: BoxRenderable): void {
    const modal = state.taskCreateModal;
    if (!modal.open) {
      return;
    }
    const accent = accentForPage("Tickets");
    const currentField = currentTaskCreateField();
    const overlay = new BoxRenderable(renderer, {
      position: "absolute",
      top: 0,
      right: 0,
      bottom: 0,
      left: 0,
      zIndex: 20,
      backgroundColor: THEME.background,
      opacity: 0.98,
      flexDirection: "column",
      justifyContent: "center",
      alignItems: "center",
      padding: 1,
    });
    const panel = new BoxRenderable(renderer, {
      border: true,
      borderColor: accent,
      focusedBorderColor: THEME.text,
      title: "Create task",
      titleColor: accent,
      backgroundColor: THEME.panel,
      width: "92%",
      maxWidth: 92,
      flexDirection: "column",
      padding: 1,
      gap: 1,
    });

    function makeFieldFrame(field: TaskCreateField, label: string): BoxRenderable {
      const active = currentField === field;
      const frame = new BoxRenderable(renderer, {
        border: true,
        borderColor: active ? accent : THEME.border,
        focusedBorderColor: THEME.text,
        title: active ? `> ${label}` : `  ${label}`,
        titleColor: active ? accent : THEME.subtle,
        backgroundColor: active ? THEME.panelAlt : THEME.panel,
        flexDirection: "column",
        padding: 1,
        gap: 1,
      });
      frame.onMouseDown = () => {
        setTaskCreateActiveField(field);
        setPageFocus("Tickets", field === "title" || field === "description" ? "input" : "scroll");
        renderPage("Tickets");
      };
      return frame;
    }

    function renderTextField(field: "title" | "description", label: string, placeholder: string): void {
      const frame = makeFieldFrame(field, label);
      const input = new InputRenderable(renderer, {
        value: field === "title" ? modal.title : modal.description,
        placeholder,
        minLength: 0,
        backgroundColor: currentField === field ? THEME.panelAlt : THEME.panel,
        textColor: THEME.text,
        focusedBackgroundColor: THEME.panelAlt,
        focusedTextColor: THEME.text,
      });
      input.on(InputRenderableEvents.INPUT, (value: string) => {
        if (field === "title") {
          state.taskCreateModal.title = value;
        } else {
          state.taskCreateModal.description = value;
        }
        state.taskCreateModal.error = null;
      });
      input.on(InputRenderableEvents.ENTER, () => {
        void submitTaskCreateModal();
      });
      if (currentField === field) {
        activeInput = input;
      }
      frame.add(input);
      panel.add(frame);
    }

    function renderOptionField(
      field: TaskCreateField,
      label: string,
      options: { name: string; description: string }[],
      selectedIndex: number,
      tabWidth: number,
    ): void {
      const frame = makeFieldFrame(field, label);
      const tab = new TabSelectRenderable(renderer, {
        options,
        tabWidth,
        height: 2,
        backgroundColor: currentField === field ? THEME.panelAlt : THEME.panel,
        textColor: THEME.text,
        focusedBackgroundColor: THEME.panelAlt,
        focusedTextColor: THEME.text,
        selectedBackgroundColor: THEME.panelAlt,
        selectedTextColor: accent,
        selectedDescriptionColor: THEME.subtle,
        showDescription: false,
        showUnderline: true,
        showScrollArrows: true,
        wrapSelection: true,
      });
      const safeSelectedIndex = Math.max(0, Math.min(selectedIndex, options.length - 1));
      tab.setSelectedIndex(safeSelectedIndex);
      frame.add(tab);
      panel.add(frame);
    }

    renderTextField("title", "Title", "Task title");
    renderTextField("description", "Description", "Optional task description");

    const typeIndex = Math.max(0, TASK_TYPE_ORDER.indexOf(modal.taskType));
    renderOptionField(
      "taskType",
      "Task type",
      TASK_TYPE_ORDER.map((type) => ({
        name: type,
        description: taskTypeRequiresRepository(type) ? "repository required" : "repository optional",
      })),
      typeIndex,
      14,
    );

    const repoChoices = taskCreateRepositoryChoices();
    const repoOptions = repoChoices.length > 0
      ? repoChoices.map((repoId) => {
          const repo = repositoryById(repoId);
          return {
            name: repo ? repo.name : "(none)",
            description: repo ? repo.path : "No repository",
          };
        })
      : [{ name: "No repositories", description: "Register one first" }];
    const repoSelectedIndex = repoChoices.length > 0 ? repoChoices.indexOf(modal.repositoryId) : 0;
    renderOptionField("repository", "Repository", repoOptions, repoSelectedIndex >= 0 ? repoSelectedIndex : 0, 18);

    renderOptionField(
      "autoRun",
      "Auto-run",
      [
        { name: "on", description: "Queue immediately" },
        { name: "off", description: "Create only" },
      ],
      modal.autoRun ? 0 : 1,
      10,
    );

    if (modal.error || modal.submitting) {
      panel.add(
        new TextRenderable(renderer, {
          content: modal.submitting ? "Creating task..." : modal.error ?? "",
          fg: modal.submitting ? THEME.accent : THEME.danger,
          wrapMode: "word",
        }),
      );
    }
    panel.add(
      new TextRenderable(renderer, {
        content: "Ctrl+Up/Down field  Ctrl+Left/Right option  Enter create  Esc cancel",
        fg: THEME.subtle,
        wrapMode: "word",
      }),
    );
    overlay.add(panel);
    pageRoot.add(overlay);
  }

  function renderTaskLogModal(pageRoot: BoxRenderable): void {
    const modal = state.taskLogModal;
    if (!modal.open) {
      return;
    }
    const accent = accentForPage("Tickets");
    const overlay = new BoxRenderable(renderer, {
      position: "absolute",
      top: 0,
      right: 0,
      bottom: 0,
      left: 0,
      zIndex: 25,
      backgroundColor: THEME.background,
      opacity: 0.98,
      flexDirection: "column",
      justifyContent: "center",
      alignItems: "center",
      padding: 1,
    });
    const panel = new BoxRenderable(renderer, {
      border: true,
      borderColor: accent,
      focusedBorderColor: THEME.text,
      title: "Codex logs",
      titleColor: accent,
      backgroundColor: THEME.panel,
      width: "94%",
      maxWidth: 110,
      flexDirection: "column",
      padding: 1,
      gap: 1,
    });
    const ticket = modal.ticket;
    const headerLines = [
      ticket ? `Task: ${ticket.title}` : "Task: (none)",
      `Run: ${modal.data?.run_id ?? "(none)"}`,
      `Path: ${modal.data?.path ?? "(not available yet)"}`,
      modal.loading ? "Loading..." : "Up/Down scroll  PageUp/PageDown jump  Ctrl+R refresh  Ctrl+P copy  Esc close",
      modal.notice ? `Status: ${modal.notice}` : "",
      modal.error ? `Error: ${modal.error}` : "",
    ].filter(Boolean);
    panel.add(
      new TextRenderable(renderer, {
        content: headerLines.join("\n"),
        fg: modal.error ? THEME.danger : THEME.subtle,
        wrapMode: "word",
      }),
    );

    const logScroll = new ScrollBoxRenderable(renderer, {
      height: 18,
      border: true,
      borderColor: THEME.border,
      focusedBorderColor: THEME.text,
      backgroundColor: THEME.background,
      padding: 1,
      scrollY: true,
      scrollX: false,
      viewportCulling: true,
      title: "Tail",
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
    activeScrollArea = logScroll;
    const lines = modal.data?.lines ?? [];
    const content = lines.length > 0
      ? lines.join("\n")
      : modal.loading
        ? "Waiting for log lines..."
        : "No Codex log lines found for this task.";
    logScroll.add(
      new TextRenderable(renderer, {
        content,
        fg: lines.length > 0 ? THEME.text : THEME.subtle,
        wrapMode: "word",
        truncate: false,
      }),
    );
    const restoreLogScroll = () => {
      if (!state.taskLogModal.open || activeScrollArea !== logScroll) {
        return;
      }
      logScroll.scrollTo(Math.max(0, state.taskLogModal.scrollOffset));
      state.taskLogModal.scrollOffset = logScroll.scrollTop;
    };
    restoreLogScroll();
    process.nextTick(restoreLogScroll);
    panel.add(logScroll);
    overlay.add(panel);
    pageRoot.add(overlay);
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
        "Press Ctrl+E or Esc to return. Ctrl+G cycles task_type. Ctrl+L opens logs. Ctrl+Enter queues the run.",
        TASK_TYPE_HOTKEY_HELP,
        "",
        `ID: ${t.id}`,
        `Title: ${t.title}`,
        `Description: ${t.description || "(none)"}`,
        `Type: ${t.task_type}    Agent: ${t.status}${t.status === "working" ? "  (agent is working)" : ""}`,
        `Repository: ${ticketRepositoryLabel(t)}`,
        t.classified_at
          ? `Classified at: ${t.classified_at}  by ${t.classification_model || "n/a"}`
          : "Classified at: (not yet)",
        t.classification_reason ? `Reason: ${t.classification_reason}` : "",
        `Created: ${t.created_at}`,
        `Updated: ${t.updated_at}`,
      ]
        .filter(Boolean)
        .join("\n");
      scroll.add(buildCard(renderer, "Task Detail", accentForPage("Tickets"), info));

      const nextIdx = (TASK_TYPE_ORDER.indexOf(t.task_type) + 1) % TASK_TYPE_ORDER.length;
      const typeCard = buildCard(
        renderer,
        "Change task type",
        taskTypeAccent(t.task_type),
        [
          `Current: ${t.task_type}`,
          "",
          `Press Ctrl+G to cycle to ${TASK_TYPE_ORDER[nextIdx]}.`,
          TASK_TYPE_HOTKEY_HELP,
          "",
          `Other actions:`,
          `  Ctrl+F - cycle repository`,
          `  Ctrl+L - open Codex logs`,
          `  Ctrl+Enter - queue classifier/Codex run`,
        ].join("\n"),
      );
      scroll.add(typeCard);

      scroll.add(
        buildCard(
          renderer,
          t.status === "working" ? "Codex is working" : "Automation status",
          t.status === "working" ? THEME.success : THEME.subtle,
          taskAutomationStatus(t),
          t.status === "working" ? THEME.success : THEME.subtle,
        ),
      );
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
    } else if (!state.tasks) {
      scroll.add(buildCard(renderer, "No tasks", accentForPage("Tickets"), "Tasks have not loaded yet — press Ctrl+R to refresh."));
    } else {
      scroll.add(
        buildCard(
          renderer,
          "Tasks grouped by type",
          accentForPage("Tickets"),
          `Each section is a task_type. ${TASK_TYPE_HOTKEY_HELP}.`,
        ),
      );
      let taskIndex = 0;
      for (const taskType of orderedTaskTypes(state.tasks)) {
        const tasks = state.tasks[taskType] ?? [];
        const body = tasks.length === 0
          ? "(empty)"
          : tasks.map((task) => {
              const isSelected = taskIndex === state.tasksSelectionIndex;
              taskIndex++;
              const description = task.description?.trim() ?? "";
              const repo = task.repository_id ? `\n  repo: ${ticketRepositoryLabel(task)}` : "";
              const extra = description ? `\n  ${description}` : "";
              const working = task.status === "working" ? " [working]" : "";
              const prefix = isSelected ? "► " : "- ";
              return prefix + task.title + working + extra + repo;
            }).join("\n\n");
        scroll.add(buildCard(renderer, `${taskType} (${tasks.length})`, taskTypeAccent(taskType), body));
      }
    }

    if (!state.detailTicket && !state.pendingAction) {
      scroll.add(
        buildCard(
          renderer,
          "Create a task",
          accentForPage("Tickets"),
          "Press Ctrl+Space to open the task form. The form owns title, description, type, repository, and auto-run for the new task.",
        ),
      );
    }
    renderTaskCreateModal(pageRoot);
    renderTaskLogModal(pageRoot);
  }

  function renderRepositoriesPage(pageRoot: BoxRenderable): void {
    const scroll = makeScrollArea(pageRoot, accentForPage("Repositories"));
    activeScrollArea = scroll;
    if (!token) {
      scroll.add(buildCard(renderer, "No token", THEME.danger, "Run nina init first so the TUI can talk to the daemon.", THEME.danger));
    } else if (state.repositories.length === 0) {
      scroll.add(buildCard(renderer, "Repositories", accentForPage("Repositories"), "No repositories registered yet."));
    } else {
      const body = state.repositories.map((repo, index) => {
        const prefix = index === state.repositoriesSelectionIndex ? "► " : "- ";
        return `${prefix}${repo.name}
  ${repo.path}
  id: ${repo.id}
${repositoryWorktreeLines(repo)}`;
      }).join("\n\n");
      scroll.add(buildCard(renderer, `Repositories (${state.repositories.length})`, accentForPage("Repositories"), body));
    }

    const input = makeInputSection(
      pageRoot,
      "Register repository",
      "Repository path | optional name",
      accentForPage("Repositories"),
    );
    activeInput = input;
    input.on(InputRenderableEvents.ENTER, (value: string) => {
      void (async () => {
        try {
          const draft = parseRepositoryDraft(value);
          if (!draft.path) {
            return;
          }
          input.value = "";
          const created = await apiFetch<Repository>(token, "/repositories", {
            method: "POST",
            body: JSON.stringify({ path: draft.path, name: draft.name || null }),
          });
          await refreshRepositories();
          state.taskDraft.repositoryId = state.taskDraft.repositoryId || created.id;
          state.banner = { kind: "success", text: `Registered repository ${created.name}.` };
          renderPage("Repositories");
        } catch (error) {
          state.lastError = error instanceof Error ? error.message : String(error);
          renderPage("Repositories");
        }
      })();
    });
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
      scroll.add(
        buildCard(
          renderer,
          "No research yet",
          accentForPage("Research"),
          "Research a topic with Codex web search. The full report and sources are written to Obsidian.",
        ),
      );
    } else {
      scroll.add(
        buildCard(
          renderer,
          "Research summary",
          accentForPage("Research"),
          state.researchReport.summary.trim() || "No summary available.",
        ),
      );
    }
    if (state.researchPending) {
      scroll.add(
        buildLoadingCard(
          state.researchPending.text,
          state.researchPending.startedAt,
          `Research • ${formatElapsed(Date.now() - state.researchPending.startedAt)}`,
        ),
      );
    }

    const input = makeInputSection(pageRoot, "Research topic", "Research with Codex and write a note into Obsidian", accentForPage("Research"));
    activeInput = input;
    input.on(InputRenderableEvents.ENTER, (value: string) => {
      void runResearch(value, input);
    });
  }

  function renderJobsPage(pageRoot: BoxRenderable): void {
    const scroll = makeScrollArea(pageRoot, accentForPage("Jobs"));
    activeScrollArea = scroll;
    if (state.jobsView === "detail") {
      const jobName = state.jobsDetailJobName;
      const job = state.jobs.find((j) => j.name === jobName) ?? null;
      const description = job ? workflowDescription(job.workflow_name) : "";
      const headerLines = job
        ? [
            `Workflow: ${job.workflow_name}`,
            description,
            "",
            `Schedule: ${job.schedule}`,
            `Enabled: ${job.enabled ? "yes" : "no"}`,
            `Last run: ${formatTime(job.last_run_at)}`,
            `Next run: ${formatTime(job.next_run_at)}`,
          ]
        : ["Job no longer exists. Press Esc or Ctrl+A to return to the list."];
      scroll.add(
        buildCard(
          renderer,
          `Job: ${jobName ?? "unknown"}`,
          accentForPage("Jobs"),
          headerLines.filter((line) => line.length > 0).join("\n"),
        ),
      );
      if (state.jobsDetailRuns.length === 0) {
        scroll.add(
          buildCard(
            renderer,
            "No runs",
            THEME.subtle,
            "No job runs have been recorded for this job yet.",
            THEME.subtle,
          ),
        );
      } else {
        for (const run of state.jobsDetailRuns) {
          const accent = run.status === "completed" ? THEME.success : THEME.subtle;
          scroll.add(
            buildCard(
              renderer,
              `Run: ${run.id.slice(0, 8)}…`,
              accent,
              [
                `Status: ${run.status}`,
                `Started: ${formatTime(run.started_at)}`,
                `Completed: ${formatTime(run.completed_at)}`,
                run.workflow_run_id ? `Workflow: ${run.workflow_run_id.slice(0, 8)}…` : "",
                run.error ? `Error: ${run.error}` : "",
              ]
                .filter((line) => line.length > 0)
                .join("\n"),
              THEME.text,
            ),
          );
        }
      }
      scroll.add(
        buildCard(
          renderer,
          "Keys",
          THEME.subtle,
          [
            "Esc or Ctrl+A back to jobs",
            "Ctrl+E run this job now",
            "Ctrl+Up/Down/PageUp/PageDown/Home/End scroll",
            "Ctrl+R refresh",
          ].join("\n"),
          THEME.subtle,
        ),
      );
      return;
    }
    if (state.jobs.length === 0) {
      scroll.add(
        buildCard(
          renderer,
          "No jobs",
          accentForPage("Jobs"),
          "No scheduled jobs were returned by the daemon.",
        ),
      );
      return;
    }
    for (let i = 0; i < state.jobs.length; i++) {
      const job = state.jobs[i];
      const isSelected = i === state.jobsSelectionIndex;
      const titlePrefix = isSelected ? "▶ " : "  ";
      const description = workflowDescription(job.workflow_name);
      const body = [
        `Workflow: ${job.workflow_name}`,
        description,
        "",
        `Schedule: ${job.schedule}`,
        `Enabled: ${job.enabled ? "yes" : "no"}`,
        `Last run: ${formatTime(job.last_run_at)}`,
        `Next run: ${formatTime(job.next_run_at)}`,
      ];
      scroll.add(
        buildCard(
          renderer,
          `${titlePrefix}${job.name}`,
          isSelected ? THEME.text : accentForPage("Jobs"),
          body.join("\n"),
        ),
      );
    }
    scroll.add(
      buildCard(
        renderer,
        "Keys",
        THEME.subtle,
        [
          "Ctrl+Up/Down select a job",
          "Ctrl+A open runs for the selected job",
          "Ctrl+E run the selected job now",
          "Esc returns to the tab strip",
          "Ctrl+R refresh",
        ].join("\n"),
        THEME.subtle,
      ),
    );
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
        "Ctrl+E transcribe + summarize    Ctrl+X stop active",
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

  function integrationStatusLabel(status: string, configured: boolean): string {
    if (!configured) {
      return "not configured";
    }
    if (status === "ok") {
      return "ok";
    }
    if (status === "failed") {
      return "failed";
    }
    return status || "unknown";
  }

  function integrationStatusColor(status: string, configured: boolean): string {
    if (!configured) {
      return THEME.subtle;
    }
    if (status === "ok") {
      return THEME.success;
    }
    if (status === "failed") {
      return THEME.danger;
    }
    return THEME.subtle;
  }

  function renderIntegrationsPage(pageRoot: BoxRenderable): void {
    const scroll = makeScrollArea(pageRoot, accentForPage("Integrations"), "Integrations (scrollable)");
    activeScrollArea = scroll;
    if (state.integrations.length === 0) {
      scroll.add(
        buildCard(
          renderer,
          "No integrations registered",
          accentForPage("Integrations"),
          "The daemon did not return any integrations. Restart it with `nina daemon start`.",
        ),
      );
    } else {
      for (const integration of state.integrations) {
        const last = integration.last_test;
        const identity = last?.identity ?? null;
        const statusLabel = integrationStatusLabel(integration.status, integration.configured);
        const accent = integrationStatusColor(integration.status, integration.configured);
        const identityLine = identity
          ? identity.email
            ? `${identity.display_name} <${identity.email}>`
            : identity.display_name
          : "—";
        const workspaceLine = identity?.workspace ? `\nWorkspace: ${identity.workspace}` : "";
        const body = [
          `Name: ${integration.name}`,
          `Auth style: ${integration.auth_style}`,
          `Configured: ${integration.configured ? "yes" : "no"}`,
          `Last test: ${last ? last.tested_at : "never"}`,
          `Latency: ${last ? `${last.latency_ms}ms` : "—"}`,
          `Identity: ${identityLine}${workspaceLine}`,
          last?.error ? `Error: ${last.error}` : "",
          `Docs: ${integration.docs_url}`,
        ]
          .filter((line) => line.length > 0)
          .join("\n");
        scroll.add(
          buildCard(
            renderer,
            `${integration.display_name}  •  ${statusLabel}`,
            accent,
            body,
          ),
        );
      }
    }
    scroll.add(
      buildCard(
        renderer,
        "Read-only",
        THEME.subtle,
        [
          "Tests run from the CLI:",
          "  nina integrations configure <name>     # set credentials",
          "  nina integrations test <name>         # run identity ping",
          "  nina integrations list                # quick status table",
          "  nina integrations history <name>      # past test results",
        ].join("\n"),
        THEME.subtle,
      ),
    );
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

  async function refreshTasks(): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    state.tasks = await apiFetch<TaskGroup>(token, "/tasks/grouped-by-type");
    if (state.detailTicket) {
      state.detailTicket = findTaskById(state.detailTicket.id) ?? state.detailTicket;
    }
  }

  async function refreshRepositories(): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run nina init first.");
    }
    state.repositories = await apiFetch<Repository[]>(token, "/repositories");
    const worktreeEntries = await Promise.all(
      state.repositories.map(async (repo) => {
        try {
          const worktrees = await apiFetch<RepositoryWorktree[]>(
            token,
            `/repositories/${encodeURIComponent(repo.id)}/worktrees`,
          );
          return { repoId: repo.id, worktrees, error: null };
        } catch (error) {
          return {
            repoId: repo.id,
            worktrees: [],
            error: error instanceof Error ? error.message : String(error),
          };
        }
      }),
    );
    state.repositoryWorktrees = {};
    state.repositoryWorktreeErrors = {};
    for (const entry of worktreeEntries) {
      state.repositoryWorktrees[entry.repoId] = entry.worktrees;
      if (entry.error) {
        state.repositoryWorktreeErrors[entry.repoId] = entry.error;
      }
    }
    if (state.repositories.length > 0) {
      if (state.repositoriesSelectionIndex < 0 || state.repositoriesSelectionIndex >= state.repositories.length) {
        state.repositoriesSelectionIndex = 0;
      }
    } else {
      state.repositoriesSelectionIndex = -1;
    }
    normalizeTaskDraftRepository();
    normalizeTaskCreateRepository();
  }

  function openTaskDetail(ticket: Ticket): void {
    state.detailTicket = ticket;
  }

  function cycleType(current: string): string {
    const idx = TASK_TYPE_ORDER.indexOf(current);
    if (idx < 0) return TASK_TYPE_ORDER[0];
    return TASK_TYPE_ORDER[(idx + 1) % TASK_TYPE_ORDER.length];
  }

  async function setTaskType(ticket: Ticket, newType: string): Promise<void> {
    if (newType === ticket.task_type) return;
    if (taskTypeRequiresRepository(newType) && !ticket.repository_id) {
      state.banner = {
        kind: "error",
        text: state.repositories.length === 0
          ? "Register a repository before setting this task type."
          : "Attach a repository with Ctrl+F before setting this task type.",
      };
      renderPage("Tickets");
      return;
    }
    try {
      const updated = await apiFetch<Ticket>(token, `/tasks/${ticket.id}`, {
        method: "PATCH",
        body: JSON.stringify({ task_type: newType }),
      });
      state.banner = { kind: "success", text: `Set ${ticket.title} to ${newType}.` };
      await refreshTasks();
      const refreshed = findTaskById(ticket.id) ?? updated;
      state.detailTicket = state.detailTicket ? refreshed : null;
      if (taskTypeRequiresRepository(newType)) {
        await queueTaskRun(refreshed);
        return;
      }
      renderPage("Tickets");
    } catch (error) {
      state.lastError = error instanceof Error ? error.message : String(error);
      renderPage("Tickets");
    }
  }

  async function queueTaskRun(ticket: Ticket): Promise<void> {
    if (taskTypeRequiresRepository(ticket.task_type) && !ticket.repository_id) {
      state.banner = { kind: "error", text: "Attach a repository before running this task." };
      renderPage("Tickets");
      return;
    }
    await apiFetch<{ status: string; task_id?: string; background?: boolean }>(
      token,
      `/tasks/${ticket.id}/run`,
      {
        method: "POST",
        body: JSON.stringify({ background: true }),
      },
    );
    state.banner = {
      kind: "info",
      text: `Queued ${ticket.title} for Nina/Codex.`,
    };
    await refreshTasks();
    const refreshed = findTaskById(ticket.id);
    if (state.detailTicket && refreshed) {
      state.detailTicket = refreshed;
    }
    renderPage("Tickets");
  }


  async function cycleTaskRepository(ticket: Ticket): Promise<void> {
    if (state.repositories.length === 0) {
      state.banner = { kind: "info", text: "Register a repository first." };
      renderPage("Tickets");
      return;
    }
    const repoIds = state.repositories.map((repo) => repo.id);
    const choices = taskTypeRequiresRepository(ticket.task_type) ? repoIds : [null, ...repoIds];
    const currentIndex = choices.indexOf(ticket.repository_id);
    const nextRepositoryId = choices[(currentIndex + 1 + choices.length) % choices.length] ?? null;
    try {
      const updated = await apiFetch<Ticket>(token, `/tasks/${ticket.id}`, {
        method: "PATCH",
        body: JSON.stringify({ repository_id: nextRepositoryId }),
      });
      state.banner = { kind: "success", text: `Repository set to ${ticketRepositoryLabel(updated)}.` };
      await refreshTasks();
      const refreshed = findTaskById(ticket.id) ?? updated;
      if (state.detailTicket) {
        state.detailTicket = refreshed;
      }
      renderPage("Tickets");
    } catch (error) {
      state.lastError = error instanceof Error ? error.message : String(error);
      renderPage("Tickets");
    }
  }

  async function classifySelected(): Promise<void> {
    const selected = getSelectedTask();
    if (!selected) {
      state.banner = { kind: "info", text: "Select a task first." };
      return;
    }
    try {
      state.banner = { kind: "info", text: `Classifying ${selected.ticket.title}…` };
      renderPage("Tickets");
      const result = await apiFetch<{ status: string; output?: { task_type?: string } }>(
        token,
        `/tasks/${selected.ticket.id}/classify`,
        { method: "POST", body: JSON.stringify({}) },
      );
      if (result.status === "completed" && result.output?.task_type) {
        state.banner = {
          kind: "success",
          text: `Classified ${selected.ticket.title} as ${result.output.task_type}.`,
        };
      } else {
        state.banner = { kind: "info", text: `Classification: ${result.status}` };
      }
      await refreshTasks();
      renderPage("Tickets");
    } catch (error) {
      state.lastError = error instanceof Error ? error.message : String(error);
      renderPage("Tickets");
    }
  }

  async function routeSelected(): Promise<void> {
    const selected = getSelectedTask();
    if (!selected) {
      state.banner = { kind: "info", text: "Select a task first." };
      return;
    }
    if (taskTypeRequiresRepository(selected.ticket.task_type) && !selected.ticket.repository_id) {
      state.banner = { kind: "error", text: "Attach a repository before running this task." };
      renderPage("Tickets");
      return;
    }
    if (selected.ticket.task_type === "reminder"
        || selected.ticket.task_type === "blocked") {
      state.banner = {
        kind: "info",
        text: `AI does not run ${selected.ticket.task_type} tasks - please handle it yourself.`,
      };
      renderPage("Tickets");
      return;
    }
    try {
      state.banner = { kind: "info", text: `Queueing ${selected.ticket.title}...` };
      renderPage("Tickets");
      await queueTaskRun(selected.ticket);
    } catch (error) {
      state.lastError = error instanceof Error ? error.message : String(error);
      renderPage("Tickets");
    }
  }


  async function refreshJobs(): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    state.jobs = await apiFetch<Job[]>(token, "/jobs");
    state.workflows = await apiFetch<WorkflowInfo[]>(token, "/workflows").then(
      (list) => Object.fromEntries(list.map((w) => [w.name, w.description])),
    );
    if (state.jobs.length > 0) {
      if (state.jobsSelectionIndex < 0 || state.jobsSelectionIndex >= state.jobs.length) {
        state.jobsSelectionIndex = 0;
      }
    } else {
      state.jobsSelectionIndex = 0;
    }
  }

  function workflowDescription(name: string): string {
    return state.workflows[name] ?? "";
  }

  async function refreshJobRuns(jobName: string): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    state.jobsDetailRuns = await apiFetch<JobRun[]>(
      token,
      `/job-runs?job_name=${encodeURIComponent(jobName)}&limit=50`,
    );
  }

  async function triggerJobRun(jobName: string): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    const result = await apiFetch<{ id: string; status: string; job_name: string }>(
      token,
      `/jobs/${encodeURIComponent(jobName)}/run`,
      { method: "POST", body: JSON.stringify({}) },
    );
    state.banner = {
      kind: "success",
      text: `Triggered ${result.job_name} (run ${result.id} → ${result.status}).`,
    };
    if (state.jobsView === "detail" && state.jobsDetailJobName === jobName) {
      await refreshJobRuns(jobName);
    }
    await refreshJobs();
    renderPage(state.currentPage);
  }

  async function refreshMeetings(): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    const response = await apiFetch<{ meetings: Meeting[] }>(token, "/meetings?limit=20");
    state.meetings = response.meetings || [];
  }

  async function refreshIntegrations(): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    const response = await apiFetch<IntegrationsResponse>(token, "/integrations");
    state.integrations = response.integrations || [];
  }

  async function triggerMeetingPipeline(meetingId: string): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    const result = await apiFetch<{
      status: string;
      output?: { note_path?: string | null };
    }>(
      token,
      `/meetings/${meetingId}/pipeline`,
      { method: "POST", body: JSON.stringify({}) },
    );
    if (result.status !== "completed") {
      throw new Error(`pipeline did not complete (status: ${result.status})`);
    }
    state.banner = {
      kind: "success",
      text: `Transcribed + summarized ${meetingId}.`,
    };
    if (result.output?.note_path) {
      state.banner = { ...state.banner, text: `${state.banner.text} Note: ${result.output.note_path}` };
    }
    await refreshMeetings();
    renderPage("Meetings");
  }

  async function openResearchInObsidian(notePath?: string): Promise<void> {
    if (!token) {
      throw new Error("No Nina token found. Run `nina init` first.");
    }
    const path = notePath ?? state.researchReport?.note_path;
    if (!path) {
      throw new Error("No research note has been written yet.");
    }
    await apiFetch<{ opened: boolean }>(token, "/search/open", {
      method: "POST",
      body: JSON.stringify({ path }),
    });
    state.banner = { kind: "info", text: `Requested Obsidian to open ${path}` };
    renderPage("Research");
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
      await refreshMeetings();
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
    const pending = { text, startedAt: Date.now() };
    if (kind === "chat") {
      state.chatPending = pending;
    } else {
      state.agentPending = pending;
    }
    renderPage(kind === "chat" ? "Chat" : "Agent");
  }

  function stopPending(kind: "chat" | "agent"): void {
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
      state.researchPending = { text: topic, startedAt: Date.now() };
      input.value = "";
      renderPage("Research");
      const report = await apiFetch<ResearchRunResult>(token, "/research/run", {
        method: "POST",
        body: JSON.stringify({ topic }),
      });
      state.researchReport = report;
      state.banner = { kind: "success", text: `Research note written to ${report.note_path}` };
      try {
        await openResearchInObsidian(report.note_path);
        state.banner = { kind: "success", text: `Research note written and requested Obsidian to open ${report.note_path}` };
      } catch (openError) {
        const detail = openError instanceof Error ? openError.message : String(openError);
        state.banner = { kind: "success", text: `Research note written to ${report.note_path}. Open in Obsidian failed: ${detail}` };
      }
      state.researchPending = null;
      renderPage("Research");
    } catch (error) {
      state.researchPending = null;
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
      case "Repositories":
        renderRepositoriesPage(pageRoot);
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
      case "Integrations":
        renderIntegrationsPage(pageRoot);
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
        await refreshRepositories();
        await refreshTasks();
        break;
      case "Repositories":
        await refreshRepositories();
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
        if (state.jobsView === "detail" && state.jobsDetailJobName) {
          await refreshJobRuns(state.jobsDetailJobName);
        }
        break;
      case "Integrations":
        await refreshIntegrations();
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
    if (state.taskLogModal.open && handleTaskLogModalKey(key)) {
      return;
    }
    if (state.taskCreateModal.open && handleTaskCreateModalKey(key)) {
      return;
    }
    if (state.currentPage === "Tickets" && isCtrlSpace(key) && !state.pendingAction) {
      openTaskCreateModal();
      consumeKey(key);
      return;
    }

    const ticketTypeShortcutIndex = ctrlDigitIndex(key);
    if (
      state.currentPage === "Tickets"
      && ticketTypeShortcutIndex !== null
      && ticketTypeShortcutIndex < TASK_TYPE_ORDER.length
    ) {
      const selected = getSelectedTask();
      if (selected) {
        void setTaskType(selected.ticket, TASK_TYPE_ORDER[ticketTypeShortcutIndex]);
        consumeKey(key);
        return;
      }
    }

    const pageShortcutIndex = ctrlDigitIndex(key);
    if (pageShortcutIndex !== null) {
      const page = PAGE_NAMES[pageShortcutIndex];
      if (page) {
        setPageFocus(page, PAGE_DEFAULT_FOCUS[page]);
        tabs.setSelectedIndex(pageShortcutIndex);
      }
      consumeKey(key);
      return;
    }
    if (isCtrlKey(key, "g") && state.currentPage !== "Tickets") {
      if (activeInput) {
        activeInput.blur();
      }
      setPageFocus(state.currentPage, "tabs");
      tabs.focus();
      consumeKey(key);
      return;
    }
    if (isCtrlKey(key, "b")) {
      if (activeInput) {
        activeInput.blur();
      }
      if (activeScrollArea) {
        setPageFocus(state.currentPage, "scroll");
        activeScrollArea.focus();
      } else {
        state.banner = { kind: "info", text: "This page does not expose a body focus target." };
        renderPage(state.currentPage);
      }
      consumeKey(key);
      return;
    }
    if (isCtrlKey(key, "f") && state.currentPage !== "Tickets") {
      const input = state.currentPage === "Config" ? configInput ?? activeInput : activeInput;
      if (input) {
        setPageFocus(state.currentPage, "input");
        input.focus();
      } else {
        state.banner = { kind: "info", text: "This page does not expose a primary field focus target." };
        renderPage(state.currentPage);
      }
      consumeKey(key);
      return;
    }
    if (isCtrlKey(key, "k") || (key.name === "?" && !key.ctrl && !key.meta && !key.option && !key.super)) {
      state.banner = {
        kind: "info",
        text: `${globalShortcutHelp()}\n${PAGE_HELP[state.currentPage]}`,
      };
      renderPage(state.currentPage);
      consumeKey(key);
      return;
    }
    const tabMoveDirection = tabDirection(key);
    if (tabMoveDirection !== null) {
      moveTabSelection(tabs, tabMoveDirection);
      consumeKey(key);
      return;
    }
    const pageScrollKey = scrollPageKey(key);
    if (pageScrollKey && handleScrollKey(pageScrollKey, Boolean(key.ctrl))) {
      consumeKey(key);
      return;
    }
    const lineScrollDirection = ctrlLineScrollDirection(key);
    if (lineScrollDirection !== null && state.currentPage !== "Tickets" && handleLineScroll(lineScrollDirection)) {
      consumeKey(key);
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
      if (state.pendingAction) {
        state.pendingAction = null;
        renderPage("Tickets");
        consumeKey(key);
        return;
      }
      if (state.currentPage === "Jobs" && state.jobsView === "detail") {
        state.jobsView = "list";
        state.jobsDetailJobName = null;
        renderPage("Jobs");
        consumeKey(key);
        return;
      }
      if (state.currentPage === "Tickets" && state.detailTicket) {
        state.detailTicket = null;
        renderPage("Tickets");
        consumeKey(key);
        return;
      }
      if (activeInput) {
        activeInput.blur();
      }
      setPageFocus(state.currentPage, "tabs");
      tabs.focus();
      consumeKey(key);
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
    if (state.currentPage === "Research" && key.ctrl && key.name === "o") {
      void openResearchInObsidian().catch((err: unknown) => {
        state.lastError = err instanceof Error ? err.message : String(err);
        renderPage("Research");
      });
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
      if (key.name === "e" && selected) {
        // Ctrl+E — transcribe + summarize (pipeline)
        void triggerMeetingPipeline(selected.id).catch((err: unknown) => {
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
    if (state.currentPage === "Jobs") {
      // Ctrl+Up/Down navigate the jobs list. In detail view the keys
      // fall through to the general Ctrl+Up/Down scroll handler below.
      if (
        key.ctrl &&
        !key.meta &&
        !key.option &&
        !key.super &&
        (key.name === "up" || key.name === "down") &&
        state.jobsView === "list"
      ) {
        if (state.jobs.length > 0) {
          const delta = key.name === "up" ? -1 : 1;
          state.jobsSelectionIndex =
            (state.jobsSelectionIndex + delta + state.jobs.length) % state.jobs.length;
          renderPage("Jobs");
        }
        key.preventDefault();
        key.stopPropagation();
        return;
      }
      // Esc in detail mode returns to the list before the global Esc
      // (which always jumps focus to the tab strip).
      if (
        state.jobsView === "detail" &&
        (key.name === "escape" || key.name === "esc")
      ) {
        state.jobsView = "list";
        state.jobsDetailJobName = null;
        renderPage("Jobs");
        key.preventDefault();
        key.stopPropagation();
        return;
      }
      if (key.ctrl && key.name === "a") {
        // Ctrl+A — toggle between the jobs list and a job's runs view.
        if (state.jobsView === "list") {
          const job = state.jobs[state.jobsSelectionIndex];
          if (!job) {
            state.lastError = "No job selected.";
            renderPage("Jobs");
            key.preventDefault();
            key.stopPropagation();
            return;
          }
          state.jobsDetailJobName = job.name;
          state.jobsView = "detail";
          renderPage("Jobs");
          void refreshJobRuns(job.name).catch((err: unknown) => {
            state.lastError = err instanceof Error ? err.message : String(err);
            renderPage("Jobs");
          });
        } else {
          state.jobsView = "list";
          state.jobsDetailJobName = null;
          renderPage("Jobs");
        }
        key.preventDefault();
        key.stopPropagation();
        return;
      }
      if (key.ctrl && key.name === "e") {
        // Ctrl+E — run the selected job (or the open detail job) now.
        const jobName =
          state.jobsView === "detail"
            ? state.jobsDetailJobName
            : state.jobs[state.jobsSelectionIndex]?.name;
        if (!jobName) {
          state.lastError = "No job selected.";
          renderPage("Jobs");
          key.preventDefault();
          key.stopPropagation();
          return;
        }
        void triggerJobRun(jobName).catch((err: unknown) => {
          state.lastError = err instanceof Error ? err.message : String(err);
          renderPage("Jobs");
        });
        key.preventDefault();
        key.stopPropagation();
        return;
      }
    }
    if (state.currentPage === "Tickets" && key.ctrl && key.name === "d" && !state.pendingAction) {
      const selected = state.detailTicket ?? getSelectedTask()?.ticket ?? null;
      if (selected) {
        state.pendingAction = { type: "delete", ticket: selected };
        renderPage("Tickets");
      }
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.currentPage === "Tickets" && key.ctrl && (key.name === "up" || key.name === "down")) {
      const tasks = getVisibleTasks();
      if (tasks.length === 0) return;
      const direction = key.name === "up" ? -1 : 1;
      if (state.tasksSelectionIndex === -1) {
        state.tasksSelectionIndex = direction > 0 ? 0 : tasks.length - 1;
      } else {
        state.tasksSelectionIndex = (state.tasksSelectionIndex + direction + tasks.length) % tasks.length;
      }
      renderPage("Tickets");
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.currentPage === "Tickets" && key.ctrl && key.name === "l" && !state.pendingAction) {
      const selected = state.detailTicket ?? getSelectedTask()?.ticket ?? null;
      if (selected) {
        openTaskLogModal(selected);
      } else {
        state.banner = { kind: "info", text: "Select a task first." };
        renderPage("Tickets");
      }
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.currentPage === "Tickets" && key.ctrl && key.name === "g" && !state.pendingAction) {
      const selected = state.detailTicket ?? getSelectedTask()?.ticket ?? null;
      if (selected) {
        void setTaskType(selected, cycleType(selected.task_type));
      } else {
        state.banner = { kind: "info", text: "Select a task, or press Ctrl+Space to create one." };
        renderPage("Tickets");
      }
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.currentPage === "Tickets" && key.ctrl && (key.name === "return" || key.name === "enter" || key.name === "kpenter") && !state.detailTicket) {
      void routeSelected();
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.currentPage === "Tickets" && key.ctrl && key.name === "y" && !state.detailTicket && !state.pendingAction) {
      state.banner = { kind: "info", text: "Auto-run is set in the create form. Press Ctrl+Space to create a task." };
      renderPage("Tickets");
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.currentPage === "Tickets" && key.ctrl && key.name === "f" && !state.pendingAction) {
      const selected = state.detailTicket ?? getSelectedTask()?.ticket ?? null;
      if (selected) {
        void cycleTaskRepository(selected);
      } else {
        state.banner = { kind: "info", text: "Select a task, or press Ctrl+Space to create one." };
        renderPage("Tickets");
      }
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.currentPage === "Repositories" && key.ctrl && (key.name === "up" || key.name === "down")) {
      if (state.repositories.length === 0) return;
      const direction = key.name === "up" ? -1 : 1;
      if (state.repositoriesSelectionIndex === -1) {
        state.repositoriesSelectionIndex = direction > 0 ? 0 : state.repositories.length - 1;
      } else {
        state.repositoriesSelectionIndex = (state.repositoriesSelectionIndex + direction + state.repositories.length) % state.repositories.length;
      }
      renderPage("Repositories");
      key.preventDefault();
      key.stopPropagation();
      return;
    }
    if (state.pendingAction && (key.name === "y" || key.name === "Y")) {
      const { type, ticket } = state.pendingAction;
      state.pendingAction = null;
      void (async () => {
        try {
          const endpoint = type === "delete" ? `/tasks/${ticket.id}` : `/tasks/${ticket.id}/archive`;
          const method = type === "delete" ? "DELETE" : "POST";
          await apiFetch(token, endpoint, { method });
          state.banner = { kind: "success", text: `${type === "delete" ? "Deleted" : "Archived"} task ${ticket.id}` };
          state.tasksSelectionIndex = -1;
          await refreshTasks();
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
    if (state.currentPage === "Tickets" && key.ctrl && key.name === "a") {
      const selected = getSelectedTask();
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
        const selected = getSelectedTask();
        if (selected) {
          openTaskDetail(selected.ticket);
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

