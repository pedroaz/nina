#![allow(dead_code)]

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, Deserialize, Default)]
pub struct HealthResponse {
    pub status: String,
    pub profile: Option<String>,
    pub vault_path: Option<String>,
    pub vault_configured: Option<bool>,
    pub transcription: Option<TranscriptionHealth>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct TranscriptionHealth {
    pub backend: String,
    pub model: String,
    pub device: String,
    pub compute_type: String,
    pub available: bool,
    pub detail: Option<String>,
    pub provider_class: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct RuntimeState {
    pub daemon_host: Option<String>,
    pub daemon_port: Option<u16>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct Ticket {
    pub id: String,
    pub repository_id: Option<String>,
    pub repository_name: Option<String>,
    pub repository_path: Option<String>,
    pub title: String,
    #[serde(default)]
    pub description: String,
    pub task_type: String,
    pub status: String,
    pub note_path: Option<String>,
    pub classified_at: Option<String>,
    pub classification_reason: Option<String>,
    pub classification_model: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

pub type TaskGroup = BTreeMap<String, Vec<Ticket>>;

#[derive(Debug, Clone, Serialize)]
pub struct TaskCreateRequest {
    pub title: String,
    pub description: String,
    pub repository_id: Option<String>,
    pub task_type: Option<String>,
    pub auto_classify: bool,
    pub auto_run: bool,
    pub auto_run_background: bool,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct TaskUpdateRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub task_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub repository_id: Option<Option<String>>,
}

#[derive(Debug, Clone, Serialize)]
pub struct TaskRunRequest {
    pub background: bool,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct CodexTaskLogRun {
    pub run_id: String,
    pub path: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct CodexTaskLogsResponse {
    pub task_id: String,
    pub run_id: Option<String>,
    pub path: String,
    #[serde(default)]
    pub lines: Vec<String>,
    pub tail: i32,
    #[serde(default)]
    pub runs: Vec<CodexTaskLogRun>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct Repository {
    pub id: String,
    pub name: String,
    pub path: String,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct RepositoryCreateRequest {
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct RepositoryWorktree {
    pub path: String,
    pub head: Option<String>,
    pub branch: Option<String>,
    pub bare: bool,
    pub detached: bool,
    pub locked: Option<String>,
    pub prunable: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct SessionMessage {
    pub id: String,
    pub session_id: String,
    pub role: String,
    pub content: String,
    #[serde(default)]
    pub metadata: Value,
    pub created_at: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct SessionRecord {
    pub id: String,
    pub mode: String,
    pub title: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    pub completed_at: Option<String>,
    #[serde(default)]
    pub messages: Vec<SessionMessage>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SessionCreateRequest {
    pub mode: String,
    pub title: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SessionMessageCreateRequest {
    pub content: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct VaultSource {
    pub path: String,
    pub title: Option<String>,
    pub nina_type: Option<String>,
    pub snippet: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct ToolInvocation {
    pub id: Option<String>,
    pub name: String,
    pub preview: Option<String>,
    #[serde(default)]
    pub arguments: Value,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct CommandResult {
    pub command: String,
    pub exit_code: i32,
    #[serde(default)]
    pub stdout: String,
    #[serde(default)]
    pub stderr: String,
    pub created_id: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct SessionSendResponse {
    pub session: SessionRecord,
    pub assistant: SessionMessage,
    #[serde(default)]
    pub sources: Vec<VaultSource>,
    #[serde(default)]
    pub tools_used: Vec<ToolInvocation>,
    #[serde(default)]
    pub commands: Vec<CommandResult>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct ResearchSource {
    pub title: String,
    pub url: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct ResearchRunResult {
    pub note_path: String,
    pub summary: String,
    #[serde(default)]
    pub sources: Vec<ResearchSource>,
    pub workflow_run_id: Option<String>,
    pub status: Option<String>,
    pub created_at: Option<String>,
    pub provider: Option<String>,
    pub model: Option<String>,
    pub search_mode: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ResearchRunRequest {
    pub topic: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub search_mode: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct WorkflowInfo {
    pub name: String,
    pub description: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct Job {
    pub name: String,
    pub workflow_name: String,
    pub schedule: String,
    pub enabled: bool,
    pub last_run_at: Option<String>,
    pub next_run_at: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct JobRun {
    pub id: String,
    pub job_name: String,
    pub status: String,
    pub workflow_run_id: Option<String>,
    pub started_at: Option<String>,
    pub completed_at: Option<String>,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct Meeting {
    pub id: String,
    pub title: String,
    pub status: String,
    pub source: String,
    pub device_name: Option<String>,
    pub started_at: String,
    pub ended_at: Option<String>,
    pub duration_seconds: Option<f64>,
    pub audio_path: String,
    pub audio_size_bytes: Option<u64>,
    pub audio_format: String,
    pub sample_rate: u32,
    pub channels: u32,
    pub transcript_path: Option<String>,
    pub summary_path: Option<String>,
    pub transcript_note_path: Option<String>,
    pub summary_note_path: Option<String>,
    pub workflow_run_id: Option<String>,
    pub error: Option<String>,
    pub note_path: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct VoiceCapture {
    pub id: String,
    pub title: String,
    pub status: String,
    pub source: String,
    pub device_name: Option<String>,
    pub started_at: String,
    pub ended_at: Option<String>,
    pub duration_seconds: Option<f64>,
    pub audio_path: String,
    pub audio_size_bytes: Option<u64>,
    pub audio_format: String,
    pub sample_rate: u32,
    pub channels: u32,
    pub transcript_path: Option<String>,
    pub transcript_note_path: Option<String>,
    pub language: Option<String>,
    pub model: Option<String>,
    pub error: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct VoiceTranscription {
    #[serde(flatten)]
    pub capture: VoiceCapture,
    #[serde(default)]
    pub transcript: Option<String>,
    #[serde(default)]
    pub transcript_missing: bool,
    pub transcript_error: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct VoiceTranscriptionsResponse {
    #[serde(default)]
    pub transcriptions: Vec<VoiceTranscription>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct VoiceActiveResponse {
    #[serde(default)]
    pub capture: Option<VoiceCapture>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct VoiceTranscriptionsDeleteResponse {
    pub deleted: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct VoiceRecordRequest {
    pub title: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct VoiceTranscribeRequest {
    pub save_note: bool,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct VoiceTranscribeResult {
    pub capture: VoiceCapture,
    pub transcript: String,
    pub transcript_path: String,
    pub segments_path: String,
    pub transcript_note_path: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct MeetingsResponse {
    #[serde(default)]
    pub meetings: Vec<Meeting>,
}

#[derive(Debug, Clone, Serialize)]
pub struct MeetingRecordRequest {
    pub title: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct IntegrationIdentity {
    pub account_id: String,
    pub display_name: String,
    pub email: Option<String>,
    pub workspace: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct IntegrationTestSummary {
    pub status: String,
    pub latency_ms: f64,
    pub identity: Option<IntegrationIdentity>,
    pub error: Option<String>,
    pub tested_at: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct IntegrationCredentialField {
    pub name: String,
    pub label: String,
    pub secret: bool,
    pub required: bool,
    pub placeholder: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct IntegrationRecord {
    pub name: String,
    pub display_name: String,
    pub description: String,
    pub docs_url: String,
    pub auth_style: String,
    #[serde(default)]
    pub credential_fields: Vec<IntegrationCredentialField>,
    #[serde(default)]
    pub configured_fields: BTreeMap<String, bool>,
    pub configured: bool,
    pub status: String,
    pub last_test: Option<IntegrationTestSummary>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct IntegrationsResponse {
    #[serde(default)]
    pub integrations: Vec<IntegrationRecord>,
}

#[derive(Debug, Clone, Serialize)]
pub struct IntegrationCredentialsUpdate {
    pub credentials: BTreeMap<String, String>,
    pub merge: bool,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct ConfigSnapshot {
    pub profile: String,
    pub config_dir: String,
    pub config_path: String,
    pub vault_path: String,
    pub database_path: String,
    pub daemon_host: String,
    pub daemon_port: u16,
    pub llm: LlmConfig,
    pub research: ResearchConfig,
    pub scheduler: SchedulerConfig,
    pub transcription: TranscriptionConfig,
    pub meetings: MeetingsConfig,
    pub voice: VoiceConfig,
    pub codex: CodexConfig,
    pub log_level: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct LlmConfig {
    pub provider: String,
    pub model: String,
    pub base_url: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct ResearchConfig {
    pub provider: String,
    pub model: String,
    pub search_mode: String,
    pub timeout_seconds: f64,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct SchedulerConfig {
    pub daily_summary_time: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct TranscriptionConfig {
    pub backend: String,
    pub model: String,
    pub device: String,
    pub compute_type: String,
    pub language: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct MeetingsConfig {
    pub default_source: String,
    pub auto_summarize: bool,
    pub sample_rate: u32,
    pub channels: u32,
    pub open_command: String,
    pub play_command: String,
    pub default_gain: f64,
    pub auto_normalize: bool,
    pub normalize_target_dbfs: f64,
    pub noise_reduction: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct VoiceConfig {
    pub global_hotkey_enabled: bool,
    pub global_hotkey: String,
    pub insert_mode: String,
    pub preserve_clipboard: bool,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct CodexConfig {
    pub enabled: bool,
    pub binary_path: String,
    pub host: String,
    pub port: u16,
    pub username: String,
    pub password_ref: String,
    pub startup_timeout_seconds: f64,
    pub shutdown_timeout_seconds: f64,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct ConfigUpdateResponse {
    pub config: ConfigSnapshot,
    #[serde(default)]
    pub changed_fields: Vec<String>,
    pub restart_required: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct OpenNoteRequest {
    pub path: String,
}
