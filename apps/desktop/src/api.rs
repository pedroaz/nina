use std::{
    env, fs,
    path::{Path, PathBuf},
    time::Duration,
};

use serde::{de::DeserializeOwned, Serialize};
use serde_json::{json, Value};
use thiserror::Error;
use ureq::{Agent, AgentBuilder, Error as UreqError, Request};

use crate::models::{
    CodexTaskLogsResponse, ConfigSnapshot, ConfigUpdateResponse, HealthResponse,
    IntegrationCredentialsUpdate, IntegrationTestSummary, IntegrationsResponse, Job, JobRun,
    Meeting, MeetingRecordRequest, MeetingsResponse, OpenNoteRequest, Repository,
    RepositoryCreateRequest, RepositoryWorktree, ResearchRunRequest, ResearchRunResult,
    RuntimeState, SessionCreateRequest, SessionMessageCreateRequest, SessionRecord,
    SessionSendResponse, TaskCreateRequest, TaskGroup, TaskRunRequest, TaskUpdateRequest, Ticket,
    VoiceCapture, VoiceRecordRequest, VoiceTranscribeRequest, VoiceTranscribeResult, WorkflowInfo,
};

pub type ApiResult<T> = Result<T, ApiError>;

#[derive(Debug, Error)]
pub enum ApiError {
    #[error("daemon request failed: {0}")]
    Http(String),
    #[error("daemon returned status {status}: {detail}")]
    Status { status: u16, detail: String },
    #[error("invalid daemon response: {0}")]
    Decode(String),
}

#[derive(Debug, Clone)]
pub struct ApiClient {
    agent: Agent,
    base_url: String,
    token: String,
}

impl ApiClient {
    pub fn discover() -> Self {
        let config_dir = config_dir();
        let base_url = discover_api_base(&config_dir);
        let token = fs::read_to_string(config_dir.join("token"))
            .unwrap_or_default()
            .trim()
            .to_owned();
        Self {
            agent: AgentBuilder::new()
                .timeout(Duration::from_secs(900))
                .build(),
            base_url,
            token,
        }
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    pub fn has_token(&self) -> bool {
        !self.token.is_empty()
    }

    pub fn health(&self) -> ApiResult<HealthResponse> {
        self.get("/health")
    }

    pub fn config(&self) -> ApiResult<ConfigSnapshot> {
        self.get("/config")
    }

    pub fn update_config(&self, patch: Value) -> ApiResult<ConfigUpdateResponse> {
        self.patch_json("/config", &patch)
    }

    pub fn tasks_grouped_by_type(&self) -> ApiResult<TaskGroup> {
        self.get("/tasks/grouped-by-type")
    }

    pub fn create_task(&self, request: TaskCreateRequest) -> ApiResult<Ticket> {
        self.post_json("/tasks", &request)
    }

    pub fn patch_task(&self, task_id: &str, request: TaskUpdateRequest) -> ApiResult<Ticket> {
        self.patch_json(&format!("/tasks/{}", encode(task_id)), &request)
    }

    pub fn classify_task(&self, task_id: &str) -> ApiResult<Value> {
        self.post_json(&format!("/tasks/{}/classify", encode(task_id)), &json!({}))
    }

    pub fn run_task(&self, task_id: &str) -> ApiResult<Value> {
        self.post_json(
            &format!("/tasks/{}/run", encode(task_id)),
            &TaskRunRequest { background: true },
        )
    }

    pub fn archive_task(&self, task_id: &str) -> ApiResult<Ticket> {
        self.post_json(&format!("/tasks/{}/archive", encode(task_id)), &json!({}))
    }

    pub fn delete_task(&self, task_id: &str) -> ApiResult<Value> {
        self.delete(&format!("/tasks/{}", encode(task_id)))
    }

    pub fn task_logs(&self, task_id: &str, tail: i32) -> ApiResult<CodexTaskLogsResponse> {
        self.get(&format!(
            "/tasks/{}/codex-logs?tail={}",
            encode(task_id),
            tail
        ))
    }

    pub fn repositories(&self) -> ApiResult<Vec<Repository>> {
        self.get("/repositories")
    }

    pub fn create_repository(&self, request: RepositoryCreateRequest) -> ApiResult<Repository> {
        self.post_json("/repositories", &request)
    }

    pub fn delete_repository(&self, repository_id: &str) -> ApiResult<Value> {
        self.delete(&format!("/repositories/{}", encode(repository_id)))
    }

    pub fn repository_worktrees(&self, repository_id: &str) -> ApiResult<Vec<RepositoryWorktree>> {
        self.get(&format!(
            "/repositories/{}/worktrees",
            encode(repository_id)
        ))
    }

    pub fn sessions(&self, mode: &str) -> ApiResult<Vec<SessionRecord>> {
        self.get(&format!("/sessions?mode={}", encode(mode)))
    }

    pub fn create_session(&self, mode: &str, title: &str) -> ApiResult<SessionRecord> {
        self.post_json(
            "/sessions",
            &SessionCreateRequest {
                mode: mode.to_owned(),
                title: Some(title.to_owned()),
            },
        )
    }

    pub fn get_session(&self, session_id: &str, messages_limit: usize) -> ApiResult<SessionRecord> {
        self.get(&format!(
            "/sessions/{}?messages_limit={}",
            encode(session_id),
            messages_limit
        ))
    }

    pub fn send_message(
        &self,
        session_id: &str,
        content: String,
        messages_limit: usize,
    ) -> ApiResult<SessionSendResponse> {
        self.post_json(
            &format!(
                "/sessions/{}/messages?messages_limit={}",
                encode(session_id),
                messages_limit
            ),
            &SessionMessageCreateRequest { content },
        )
    }

    pub fn cancel_session(&self, session_id: &str) -> ApiResult<Value> {
        self.post_json(
            &format!("/sessions/{}/cancel", encode(session_id)),
            &json!({}),
        )
    }

    pub fn run_research(
        &self,
        topic: String,
        search_mode: Option<String>,
    ) -> ApiResult<ResearchRunResult> {
        self.post_json("/research/run", &ResearchRunRequest { topic, search_mode })
    }

    pub fn workflows(&self) -> ApiResult<Vec<WorkflowInfo>> {
        self.get("/workflows")
    }

    pub fn jobs(&self) -> ApiResult<Vec<Job>> {
        self.get("/jobs")
    }

    pub fn job_runs(&self, job_name: &str) -> ApiResult<Vec<JobRun>> {
        self.get(&format!("/job-runs?job_name={}&limit=50", encode(job_name)))
    }

    pub fn run_job(&self, job_name: &str) -> ApiResult<JobRun> {
        self.post_json(&format!("/jobs/{}/run", encode(job_name)), &json!({}))
    }

    pub fn meetings(&self) -> ApiResult<Vec<Meeting>> {
        self.get::<MeetingsResponse>("/meetings?limit=40")
            .map(|response| response.meetings)
    }

    pub fn record_meeting(&self, title: String, source: Option<String>) -> ApiResult<Meeting> {
        self.post_json("/meetings/record", &MeetingRecordRequest { title, source })
    }

    pub fn stop_meeting(&self, meeting_id: &str) -> ApiResult<Meeting> {
        self.post_json(
            &format!("/meetings/{}/stop", encode(meeting_id)),
            &json!({}),
        )
    }

    pub fn run_meeting_pipeline(&self, meeting_id: &str) -> ApiResult<Value> {
        self.post_json(
            &format!("/meetings/{}/pipeline", encode(meeting_id)),
            &json!({}),
        )
    }

    pub fn delete_meeting(&self, meeting_id: &str) -> ApiResult<Value> {
        self.delete(&format!("/meetings/{}", encode(meeting_id)))
    }

    pub fn record_voice(&self, title: String) -> ApiResult<VoiceCapture> {
        self.post_json(
            "/voice/record",
            &VoiceRecordRequest {
                title,
                source: None,
            },
        )
    }

    pub fn stop_voice(&self, capture_id: &str) -> ApiResult<VoiceCapture> {
        self.post_json(&format!("/voice/{}/stop", encode(capture_id)), &json!({}))
    }

    pub fn transcribe_voice(
        &self,
        capture_id: &str,
        save_note: bool,
    ) -> ApiResult<VoiceTranscribeResult> {
        self.post_json(
            &format!("/voice/{}/transcribe", encode(capture_id)),
            &VoiceTranscribeRequest { save_note },
        )
    }

    pub fn integrations(&self) -> ApiResult<IntegrationsResponse> {
        self.get("/integrations")
    }

    pub fn test_integration(&self, name: &str) -> ApiResult<IntegrationTestSummary> {
        self.post_json(&format!("/integrations/{}/test", encode(name)), &json!({}))
    }

    pub fn save_integration_credentials(
        &self,
        name: &str,
        request: IntegrationCredentialsUpdate,
    ) -> ApiResult<Value> {
        self.put_json(
            &format!("/integrations/{}/credentials", encode(name)),
            &request,
        )
    }

    pub fn clear_integration_credentials(&self, name: &str) -> ApiResult<Value> {
        self.delete(&format!("/integrations/{}/credentials", encode(name)))
    }

    pub fn open_note(&self, path: String) -> ApiResult<Value> {
        self.post_json("/search/open", &OpenNoteRequest { path })
    }

    fn get<T: DeserializeOwned>(&self, path: &str) -> ApiResult<T> {
        self.request("GET", path)
            .call()
            .map_err(ApiError::from_ureq)
            .and_then(parse)
    }

    fn delete<T: DeserializeOwned>(&self, path: &str) -> ApiResult<T> {
        self.request("DELETE", path)
            .call()
            .map_err(ApiError::from_ureq)
            .and_then(parse)
    }

    fn post_json<T: DeserializeOwned, B: Serialize>(&self, path: &str, body: &B) -> ApiResult<T> {
        self.request("POST", path)
            .send_json(serde_json::to_value(body).map_err(|err| ApiError::Decode(err.to_string()))?)
            .map_err(ApiError::from_ureq)
            .and_then(parse)
    }

    fn put_json<T: DeserializeOwned, B: Serialize>(&self, path: &str, body: &B) -> ApiResult<T> {
        self.request("PUT", path)
            .send_json(serde_json::to_value(body).map_err(|err| ApiError::Decode(err.to_string()))?)
            .map_err(ApiError::from_ureq)
            .and_then(parse)
    }

    fn patch_json<T: DeserializeOwned, B: Serialize>(&self, path: &str, body: &B) -> ApiResult<T> {
        self.request("PATCH", path)
            .send_json(serde_json::to_value(body).map_err(|err| ApiError::Decode(err.to_string()))?)
            .map_err(ApiError::from_ureq)
            .and_then(parse)
    }

    fn request(&self, method: &str, path: &str) -> Request {
        let url = format!("{}{}", self.base_url, path);
        let request = self
            .agent
            .request(method, &url)
            .set("Accept", "application/json");
        if self.token.is_empty() {
            request
        } else {
            request.set("Authorization", &format!("Bearer {}", self.token))
        }
    }
}

fn parse<T: DeserializeOwned>(response: ureq::Response) -> ApiResult<T> {
    response
        .into_json()
        .map_err(|err| ApiError::Decode(err.to_string()))
}

impl ApiError {
    fn from_ureq(error: UreqError) -> Self {
        match error {
            UreqError::Status(status, response) => {
                let detail = response
                    .into_string()
                    .unwrap_or_else(|_| "request failed".to_owned());
                Self::Status { status, detail }
            }
            UreqError::Transport(err) => Self::Http(err.to_string()),
        }
    }
}

fn config_dir() -> PathBuf {
    if let Ok(value) = env::var("NINA_CONFIG_DIR") {
        return PathBuf::from(value);
    }
    let profile = env::var("NINA_PROFILE").unwrap_or_else(|_| "default".to_owned());
    let home = env::var("HOME").unwrap_or_else(|_| ".".to_owned());
    PathBuf::from(home).join(".nina").join(profile)
}

fn discover_api_base(config_dir: &Path) -> String {
    let runtime_path = config_dir.join("daemon.json");
    if let Ok(contents) = fs::read_to_string(runtime_path) {
        if let Ok(runtime) = serde_json::from_str::<RuntimeState>(&contents) {
            if let (Some(host), Some(port)) = (runtime.daemon_host, runtime.daemon_port) {
                return format!("http://{}:{}", host, port);
            }
        }
    }

    let config_path = config_dir.join("config.yaml");
    if let Ok(contents) = fs::read_to_string(config_path) {
        let mut host = None;
        let mut port = None;
        for line in contents.lines() {
            if let Some(value) = line.strip_prefix("daemon_host:") {
                host = Some(value.trim().trim_matches('"').to_owned());
            }
            if let Some(value) = line.strip_prefix("daemon_port:") {
                port = value.trim().parse::<u16>().ok();
            }
        }
        if let (Some(host), Some(port)) = (host, port) {
            return format!("http://{}:{}", host, port);
        }
    }

    "http://127.0.0.1:8765".to_owned()
}

fn encode(value: &str) -> String {
    urlencoding::encode(value).into_owned()
}
