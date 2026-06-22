export interface Ticket {
  id: string;
  repository_id: string | null;
  repository_name: string | null;
  repository_path: string | null;
  title: string;
  description: string;
  task_type: string;
  status: string;
  classified_at: string | null;
  classification_reason: string | null;
  classification_model: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskGroup {
  [taskType: string]: Ticket[];
}

export interface CodexTaskLogRun {
  run_id: string;
  path: string;
}

export interface CodexTaskLogsResponse {
  task_id: string;
  run_id: string | null;
  path: string;
  lines: string[];
  tail: number;
  runs: CodexTaskLogRun[];
}

export interface Repository {
  id: string;
  name: string;
  path: string;
  created_at: string;
  updated_at: string;
}

export interface RepositoryWorktree {
  path: string;
  head: string | null;
  branch: string | null;
  bare: boolean;
  detached: boolean;
  locked: string | null;
  prunable: string | null;
}

export interface Job {
  name: string;
  workflow_name: string;
  schedule: string;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
}

export interface JobRun {
  id: string;
  job_name: string;
  status: string;
  workflow_run_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

export interface WorkflowInfo {
  name: string;
  description: string;
}

export interface MessageMetadata {
  [key: string]: unknown;
}

export interface SessionMessage {
  id: string;
  session_id: string;
  role: string;
  content: string;
  metadata: MessageMetadata;
  created_at: string;
}

export interface SessionRecord {
  id: string;
  mode: "chat" | "agent";
  title: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  messages: SessionMessage[];
}

export interface SessionSendResponse {
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

export interface ResearchSource {
  title: string;
  url: string;
}

export interface VaultSource {
  path: string;
  title?: string;
  nina_type?: string;
  snippet?: string;
}

export interface ToolInvocation {
  id: string;
  name: string;
  preview?: string;
  arguments?: Record<string, unknown>;
}

export interface ResearchRunResult {
  note_path: string;
  summary: string;
  sources: ResearchSource[];
  workflow_run_id?: string;
  status?: string;
  created_at?: string;
  provider?: string;
  model?: string;
  search_mode?: string;
}

export interface HealthResponse {
  status: string;
  profile?: string;
  vault_path?: string;
}

export interface RuntimeState {
  profile?: string;
  config_dir?: string;
  daemon_host?: string;
  daemon_port?: number;
}

export interface ConfigSnapshot {
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
    search_mode: string;
    timeout_seconds: number;
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

export interface Meeting {
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

export interface IntegrationIdentity {
  account_id: string;
  display_name: string;
  email: string | null;
  workspace: string | null;
}

export interface IntegrationTestSummary {
  status: string;
  latency_ms: number;
  identity: IntegrationIdentity | null;
  error: string | null;
  tested_at: string;
}

export interface IntegrationRecord {
  name: string;
  display_name: string;
  description: string;
  docs_url: string;
  auth_style: string;
  configured: boolean;
  status: string;
  last_test: IntegrationTestSummary | null;
}

export interface IntegrationsResponse {
  integrations: IntegrationRecord[];
}

export interface ConfigUpdateResponse {
  config: ConfigSnapshot;
  changed_fields: string[];
  restart_required: boolean;
}

export type ConfigFieldKey =
  | "vault_path"
  | "database_path"
  | "daemon_host"
  | "daemon_port"
  | "log_level"
  | "llm.provider"
  | "llm.model"
  | "research.provider"
  | "research.model"
  | "research.search_mode"
  | "research.timeout_seconds"
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

export interface ConfigFieldDefinition {
  key: ConfigFieldKey;
  label: string;
  description: string;
  restartRequired: boolean;
  getValue: (config: ConfigSnapshot) => string;
  buildPatch: (value: string) => Record<string, unknown>;
}

export interface Banner {
  kind: "success" | "error" | "info";
  text: string;
}

export type PageName = "Tickets" | "Repositories" | "Chat" | "Agent" | "Research" | "Jobs" | "Meetings" | "Integrations" | "Config";
export type PageFocusTarget = "tabs" | "scroll" | "input" | "select";
export type MainPageFocusTarget = Exclude<PageFocusTarget, "tabs">;
