use std::{
    collections::{BTreeMap, HashMap, HashSet},
    ops::Range,
    process::Command,
    time::Duration,
};

use gpui::InteractiveElement as _;
use gpui::StatefulInteractiveElement as _;
use gpui::*;
use gpui_component::{
    button::{Button, ButtonVariants},
    h_flex,
    input::{Input, InputEvent, InputState},
    scroll::ScrollableElement,
    v_flex, Disableable, IconName, Selectable, Sizable,
};
use serde_json::{json, Value};

use crate::{
    actions::{ClearConversation, CloseModal, ToggleSidebar, DESKTOP_CONTEXT},
    api::{ApiClient, ApiError, ApiResult},
    dictation::GlobalDictationController,
    models::{
        CodexTaskLogsResponse, ConfigSnapshot, ConfigUpdateResponse, HealthResponse,
        IntegrationCredentialField, IntegrationCredentialsUpdate, IntegrationRecord,
        IntegrationsResponse, Job, JobRun, Meeting, Repository, RepositoryCreateRequest,
        RepositoryWorktree, ResearchRunResult, SessionMessage, SessionRecord, TaskCreateRequest,
        TaskGroup, TaskUpdateRequest, Ticket, WorkflowInfo,
    },
    ui::{self, color},
};

const TASK_BOARD_REFRESH_INTERVAL: Duration = Duration::from_secs(5);
const SESSION_MESSAGE_LIMIT: usize = 300;

const TASK_TYPE_ORDER: &[&str] = &[
    "unclassified",
    "coding",
    "reviewing",
    "research",
    "reminder",
    "blocked",
    "done",
];

const CONFIG_GROUPS: &[&str] = &[
    "Storage",
    "Daemon",
    "LLM",
    "Research",
    "Transcription",
    "Meetings",
    "Voice",
    "Codex",
];
const LOG_LEVEL_OPTIONS: &[&str] = &["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];
const PROVIDER_OPTIONS: &[&str] = &[
    "codex",
    "ollama",
    "openai_compatible",
    "llamacpp",
    "vllm",
    "lmstudio",
];
const RESEARCH_SEARCH_OPTIONS: &[&str] = &["live", "cached", "disabled"];
const TRANSCRIPTION_BACKEND_OPTIONS: &[&str] =
    &["local_whisper", "faster_whisper", "whisper_cli", "null"];
const TRANSCRIPTION_DEVICE_OPTIONS: &[&str] = &["cpu", "cuda"];
const TRANSCRIPTION_COMPUTE_OPTIONS: &[&str] = &["int8", "float16", "float32"];
const MEETING_SOURCE_OPTIONS: &[&str] = &["mic", "system", "mixed"];
const MEETING_CHANNEL_OPTIONS: &[&str] = &["1", "2"];
const NOISE_REDUCTION_OPTIONS: &[&str] = &["off", "ffmpeg"];
const BOOL_OPTIONS: &[&str] = &["true", "false"];
const VOICE_INSERT_MODE_OPTIONS: &[&str] = &["clipboard_paste"];
const CONFIG_FIELDS: &[ConfigField] = &[
    ConfigField::new(
        "Storage",
        "vault_path",
        "Vault path",
        "Obsidian vault root",
        false,
        ConfigEditor::Path,
    ),
    ConfigField::new(
        "Storage",
        "database_path",
        "Database path",
        "SQLite database file",
        false,
        ConfigEditor::Path,
    ),
    ConfigField::new(
        "Daemon",
        "daemon_host",
        "Daemon host",
        "Bind address on next start",
        true,
        ConfigEditor::Text,
    ),
    ConfigField::new(
        "Daemon",
        "daemon_port",
        "Daemon port",
        "Bind port on next start",
        true,
        ConfigEditor::Number,
    ),
    ConfigField::new(
        "Daemon",
        "log_level",
        "Log level",
        "Daemon logging level",
        true,
        ConfigEditor::Choice(LOG_LEVEL_OPTIONS),
    ),
    ConfigField::new(
        "LLM",
        "llm.provider",
        "LLM provider",
        "Primary chat and agent backend",
        false,
        ConfigEditor::Choice(PROVIDER_OPTIONS),
    ),
    ConfigField::new(
        "LLM",
        "llm.model",
        "LLM model",
        "Model or Codex CLI profile",
        false,
        ConfigEditor::Text,
    ),
    ConfigField::new(
        "LLM",
        "llm.base_url",
        "LLM base URL",
        "Ollama or OpenAI-compatible endpoint",
        false,
        ConfigEditor::Text,
    ),
    ConfigField::new(
        "Research",
        "research.provider",
        "Research provider",
        "Research backend",
        false,
        ConfigEditor::Choice(PROVIDER_OPTIONS),
    ),
    ConfigField::new(
        "Research",
        "research.model",
        "Research model",
        "Research model or Codex CLI profile",
        false,
        ConfigEditor::Text,
    ),
    ConfigField::new(
        "Research",
        "research.search_mode",
        "Research search mode",
        "Codex web search mode",
        false,
        ConfigEditor::Choice(RESEARCH_SEARCH_OPTIONS),
    ),
    ConfigField::new(
        "Research",
        "research.timeout_seconds",
        "Research timeout",
        "Timeout in seconds",
        false,
        ConfigEditor::Number,
    ),
    ConfigField::new(
        "Transcription",
        "transcription.backend",
        "Transcription backend",
        "Audio transcription engine",
        false,
        ConfigEditor::Choice(TRANSCRIPTION_BACKEND_OPTIONS),
    ),
    ConfigField::new(
        "Transcription",
        "transcription.model",
        "Transcription model",
        "Whisper model name",
        false,
        ConfigEditor::Text,
    ),
    ConfigField::new(
        "Transcription",
        "transcription.device",
        "Transcription device",
        "Compute device",
        false,
        ConfigEditor::Choice(TRANSCRIPTION_DEVICE_OPTIONS),
    ),
    ConfigField::new(
        "Transcription",
        "transcription.compute_type",
        "Transcription compute",
        "Model compute precision",
        false,
        ConfigEditor::Choice(TRANSCRIPTION_COMPUTE_OPTIONS),
    ),
    ConfigField::new(
        "Transcription",
        "transcription.language",
        "Transcription language",
        "Language code or auto",
        false,
        ConfigEditor::Text,
    ),
    ConfigField::new(
        "Meetings",
        "meetings.default_source",
        "Meeting source",
        "Default recording source",
        false,
        ConfigEditor::Choice(MEETING_SOURCE_OPTIONS),
    ),
    ConfigField::new(
        "Meetings",
        "meetings.auto_summarize",
        "Auto-summarize",
        "Summarize after recording",
        false,
        ConfigEditor::Choice(BOOL_OPTIONS),
    ),
    ConfigField::new(
        "Meetings",
        "meetings.sample_rate",
        "Sample rate",
        "Recording sample rate",
        false,
        ConfigEditor::Number,
    ),
    ConfigField::new(
        "Meetings",
        "meetings.channels",
        "Channels",
        "Recording channels",
        false,
        ConfigEditor::Choice(MEETING_CHANNEL_OPTIONS),
    ),
    ConfigField::new(
        "Meetings",
        "meetings.default_gain",
        "Default gain",
        "Linear gain factor",
        false,
        ConfigEditor::Number,
    ),
    ConfigField::new(
        "Meetings",
        "meetings.auto_normalize",
        "Auto-normalize",
        "Normalize audio after recording",
        false,
        ConfigEditor::Choice(BOOL_OPTIONS),
    ),
    ConfigField::new(
        "Meetings",
        "meetings.normalize_target_dbfs",
        "Normalize target dBFS",
        "Audio normalization target",
        false,
        ConfigEditor::Number,
    ),
    ConfigField::new(
        "Meetings",
        "meetings.noise_reduction",
        "Noise reduction",
        "Post-recording noise reduction",
        false,
        ConfigEditor::Choice(NOISE_REDUCTION_OPTIONS),
    ),
    ConfigField::new(
        "Voice",
        "voice.global_hotkey_enabled",
        "Global hotkey",
        "Desktop-wide dictation trigger",
        false,
        ConfigEditor::Choice(BOOL_OPTIONS),
    ),
    ConfigField::new(
        "Voice",
        "voice.global_hotkey",
        "Hotkey",
        "Shortcut shown to the desktop portal",
        false,
        ConfigEditor::Text,
    ),
    ConfigField::new(
        "Voice",
        "voice.insert_mode",
        "Insert mode",
        "How transcribed text is inserted",
        false,
        ConfigEditor::Choice(VOICE_INSERT_MODE_OPTIONS),
    ),
    ConfigField::new(
        "Voice",
        "voice.preserve_clipboard",
        "Preserve clipboard",
        "Restore previous clipboard contents after paste",
        false,
        ConfigEditor::Choice(BOOL_OPTIONS),
    ),
    ConfigField::new(
        "Codex",
        "codex.enabled",
        "Codex enabled",
        "Supervised Codex service",
        true,
        ConfigEditor::Choice(BOOL_OPTIONS),
    ),
    ConfigField::new(
        "Codex",
        "codex.binary_path",
        "Codex binary",
        "Optional Codex executable path",
        true,
        ConfigEditor::Path,
    ),
];

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
enum Page {
    Tickets,
    Repositories,
    Chat,
    Agent,
    Research,
    Meetings,
    Jobs,
    Integrations,
    Config,
}

impl Page {
    const ALL: [Page; 9] = [
        Page::Tickets,
        Page::Repositories,
        Page::Chat,
        Page::Agent,
        Page::Research,
        Page::Meetings,
        Page::Jobs,
        Page::Integrations,
        Page::Config,
    ];

    fn label(self) -> &'static str {
        match self {
            Page::Tickets => "Tasks",
            Page::Repositories => "Repositories",
            Page::Chat => "Chat",
            Page::Agent => "Agent",
            Page::Research => "Research",
            Page::Meetings => "Meetings",
            Page::Jobs => "Jobs",
            Page::Integrations => "Integrations",
            Page::Config => "Config",
        }
    }

    fn description(self) -> &'static str {
        match self {
            Page::Tickets => "Track tasks, automate coding/review stages, and inspect outcomes",
            Page::Repositories => "Register git repositories for coding and review tasks",
            Page::Chat => "Ask questions over local Nina context",
            Page::Agent => "Run safe Nina operations from natural language",
            Page::Research => "Research a topic and write an Obsidian note",
            Page::Meetings => "Record, transcribe, summarize, and open meeting notes",
            Page::Jobs => "Inspect scheduled jobs and trigger runs",
            Page::Integrations => "Read external integration health and identity pings",
            Page::Config => "Inspect and edit daemon configuration",
        }
    }

    fn icon(self) -> IconName {
        match self {
            Page::Tickets => IconName::Inbox,
            Page::Repositories => IconName::FolderOpen,
            Page::Chat => IconName::BookOpen,
            Page::Agent => IconName::Bot,
            Page::Research => IconName::Globe,
            Page::Meetings => IconName::Calendar,
            Page::Jobs => IconName::Cpu,
            Page::Integrations => IconName::Network,
            Page::Config => IconName::Settings2,
        }
    }
}

#[derive(Debug, Clone)]
struct ConfigField {
    group: &'static str,
    key: &'static str,
    label: &'static str,
    description: &'static str,
    restart_required: bool,
    editor: ConfigEditor,
}

impl ConfigField {
    const fn new(
        group: &'static str,
        key: &'static str,
        label: &'static str,
        description: &'static str,
        restart_required: bool,
        editor: ConfigEditor,
    ) -> Self {
        Self {
            group,
            key,
            label,
            description,
            restart_required,
            editor,
        }
    }

    fn allows_empty(&self) -> bool {
        matches!(self.editor, ConfigEditor::Path) || self.key == "llm.base_url"
    }
}

#[derive(Debug, Clone, Copy)]
enum ConfigEditor {
    Text,
    Path,
    Number,
    Choice(&'static [&'static str]),
}

impl ConfigEditor {
    fn label(self) -> &'static str {
        match self {
            ConfigEditor::Text => "text",
            ConfigEditor::Path => "path",
            ConfigEditor::Number => "number",
            ConfigEditor::Choice(_) => "select",
        }
    }

    fn options(self) -> Option<&'static [&'static str]> {
        match self {
            ConfigEditor::Choice(options) => Some(options),
            ConfigEditor::Text | ConfigEditor::Path | ConfigEditor::Number => None,
        }
    }
}

#[derive(Debug, Clone, Copy)]
enum ConfigRow {
    Group { group: &'static str },
    Field { field: &'static ConfigField },
}

#[derive(Debug, Clone)]
struct Banner {
    kind: BannerKind,
    text: String,
}

#[derive(Debug, Clone, Copy)]
enum BannerKind {
    Info,
    Success,
    Error,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum TaskModal {
    Create,
    Detail,
}

#[derive(Default)]
struct MessageRenderCache {
    session_id: Option<String>,
    messages: Vec<RenderedMessage>,
}

impl MessageRenderCache {
    fn sync(&mut self, session: &SessionRecord) {
        let same_session = self.session_id.as_deref() == Some(session.id.as_str());
        let same_window = self.messages.len() == session.messages.len()
            && self.messages.first().map(|message| message.id.as_str())
                == session.messages.first().map(|message| message.id.as_str())
            && self.messages.last().map(|message| message.id.as_str())
                == session.messages.last().map(|message| message.id.as_str());
        if same_session && same_window {
            return;
        }

        self.session_id = Some(session.id.clone());
        self.messages = session
            .messages
            .iter()
            .map(RenderedMessage::from_message)
            .collect();
    }

    fn clear(&mut self) {
        self.session_id = None;
        self.messages.clear();
    }

    fn len(&self) -> usize {
        self.messages.len()
    }

    fn get(&self, index: usize) -> Option<&RenderedMessage> {
        self.messages.get(index)
    }
}

struct RenderedMessage {
    id: String,
    role: String,
    is_user: bool,
    meta: String,
    body: RenderedMessageBody,
}

enum RenderedMessageBody {
    Wrapped(Vec<Vec<String>>),
    ToolPreview(String),
}

impl RenderedMessage {
    fn from_message(message: &SessionMessage) -> Self {
        let is_user = message.role == "user";
        let meta = format!(
            "{} - {}",
            message_label(&message.role),
            short_timestamp(&message.created_at)
        );
        let body = if message.role == "tool" {
            RenderedMessageBody::ToolPreview(tool_preview(&message.content))
        } else {
            let max_chars = if is_user { 58 } else { 88 };
            RenderedMessageBody::Wrapped(wrapped_paragraphs(&message.content, max_chars))
        };
        Self {
            id: message.id.clone(),
            role: message.role.clone(),
            is_user,
            meta,
            body,
        }
    }
}

pub struct NinaDesktop {
    client: ApiClient,
    focus_handle: FocusHandle,
    current_page: Page,
    sidebar_collapsed: bool,
    loading: HashSet<String>,
    banner: Option<Banner>,
    health: Option<HealthResponse>,
    config: Option<ConfigSnapshot>,
    dictation: GlobalDictationController,
    dictation_status: String,
    tasks: TaskGroup,
    repositories: Vec<Repository>,
    worktrees: HashMap<String, Vec<RepositoryWorktree>>,
    chat_session: Option<SessionRecord>,
    agent_session: Option<SessionRecord>,
    research_report: Option<ResearchRunResult>,
    meetings: Vec<Meeting>,
    jobs: Vec<Job>,
    workflows: Vec<WorkflowInfo>,
    job_runs: Vec<JobRun>,
    integrations: Vec<IntegrationRecord>,
    task_logs: Option<CodexTaskLogsResponse>,
    task_modal: Option<TaskModal>,
    task_poll_task: Option<Task<()>>,
    task_lane_scroll_handles: HashMap<String, UniformListScrollHandle>,
    chat_list_state: ListState,
    agent_list_state: ListState,
    repository_list_state: ListState,
    meeting_list_state: ListState,
    job_list_state: ListState,
    job_run_list_state: ListState,
    workflow_list_state: ListState,
    integration_list_state: ListState,
    config_list_state: ListState,
    chat_message_cache: MessageRenderCache,
    agent_message_cache: MessageRenderCache,
    config_rows: Vec<ConfigRow>,
    config_modal_open: bool,
    selected_task_id: Option<String>,
    selected_repository_id: Option<String>,
    selected_job_name: Option<String>,
    selected_meeting_id: Option<String>,
    selected_integration_name: Option<String>,
    selected_config_key: &'static str,
    config_value_source: Option<(&'static str, String)>,
    task_type: String,
    task_repository_id: Option<String>,
    task_auto_run: bool,
    meeting_source: String,
    research_search_mode: Option<String>,
    task_title: Entity<InputState>,
    task_description: Entity<InputState>,
    repository_path: Entity<InputState>,
    repository_name: Entity<InputState>,
    chat_prompt: Entity<InputState>,
    agent_prompt: Entity<InputState>,
    research_topic: Entity<InputState>,
    meeting_title: Entity<InputState>,
    integration_base_url: Entity<InputState>,
    integration_email: Entity<InputState>,
    integration_api_token: Entity<InputState>,
    integration_bot_token: Entity<InputState>,
    integration_access_token: Entity<InputState>,
    config_value: Entity<InputState>,
    _subscriptions: Vec<Subscription>,
}

impl NinaDesktop {
    pub fn new(window: &mut Window, cx: &mut Context<Self>) -> Self {
        let focus_handle = cx.focus_handle();
        window.focus(&focus_handle, cx);
        let chat_list_state = ListState::new(0, ListAlignment::Top, px(2048.));
        chat_list_state.set_follow_mode(FollowMode::Tail);
        let agent_list_state = ListState::new(0, ListAlignment::Top, px(2048.));
        agent_list_state.set_follow_mode(FollowMode::Tail);
        let repository_list_state = ListState::new(0, ListAlignment::Top, px(4096.));
        let meeting_list_state = ListState::new(0, ListAlignment::Top, px(4096.));
        let job_list_state = ListState::new(0, ListAlignment::Top, px(4096.));
        let job_run_list_state = ListState::new(0, ListAlignment::Top, px(4096.));
        let workflow_list_state = ListState::new(0, ListAlignment::Top, px(4096.));
        let integration_list_state = ListState::new(0, ListAlignment::Top, px(4096.));
        let config_rows = build_config_rows();
        let config_list_state = ListState::new(config_rows.len(), ListAlignment::Top, px(4096.));

        let mut app = Self {
            client: ApiClient::discover(),
            focus_handle,
            current_page: Page::Tickets,
            sidebar_collapsed: false,
            loading: HashSet::new(),
            banner: None,
            health: None,
            config: None,
            dictation: GlobalDictationController::new(),
            dictation_status: "Disabled".to_owned(),
            tasks: BTreeMap::new(),
            repositories: Vec::new(),
            worktrees: HashMap::new(),
            chat_session: None,
            agent_session: None,
            research_report: None,
            meetings: Vec::new(),
            jobs: Vec::new(),
            workflows: Vec::new(),
            job_runs: Vec::new(),
            integrations: Vec::new(),
            task_logs: None,
            task_modal: None,
            task_poll_task: None,
            task_lane_scroll_handles: HashMap::new(),
            chat_list_state,
            agent_list_state,
            repository_list_state,
            meeting_list_state,
            job_list_state,
            job_run_list_state,
            workflow_list_state,
            integration_list_state,
            config_list_state,
            chat_message_cache: MessageRenderCache::default(),
            agent_message_cache: MessageRenderCache::default(),
            config_rows,
            config_modal_open: false,
            selected_task_id: None,
            selected_repository_id: None,
            selected_job_name: None,
            selected_meeting_id: None,
            selected_integration_name: None,
            selected_config_key: CONFIG_FIELDS[0].key,
            config_value_source: None,
            task_type: "unclassified".to_owned(),
            task_repository_id: None,
            task_auto_run: true,
            meeting_source: "mic".to_owned(),
            research_search_mode: None,
            task_title: cx.new(|cx| InputState::new(window, cx).placeholder("Task title")),
            task_description: cx.new(|cx| InputState::new(window, cx).placeholder("Description")),
            repository_path: cx.new(|cx| InputState::new(window, cx).placeholder("/path/to/repo")),
            repository_name: cx.new(|cx| InputState::new(window, cx).placeholder("Optional name")),
            chat_prompt: cx.new(|cx| InputState::new(window, cx).placeholder("Ask Nina...")),
            agent_prompt: cx
                .new(|cx| InputState::new(window, cx).placeholder("Tell the agent what to do...")),
            research_topic: cx.new(|cx| InputState::new(window, cx).placeholder("Research topic")),
            meeting_title: cx.new(|cx| InputState::new(window, cx).placeholder("Meeting title")),
            integration_base_url: cx
                .new(|cx| InputState::new(window, cx).placeholder("https://example.atlassian.net")),
            integration_email: cx
                .new(|cx| InputState::new(window, cx).placeholder("name@example.com")),
            integration_api_token: cx.new(|cx| {
                InputState::new(window, cx)
                    .placeholder("Atlassian API token")
                    .masked(true)
            }),
            integration_bot_token: cx.new(|cx| {
                InputState::new(window, cx)
                    .placeholder("xoxb-...")
                    .masked(true)
            }),
            integration_access_token: cx.new(|cx| {
                InputState::new(window, cx)
                    .placeholder("Microsoft Graph access token")
                    .masked(true)
            }),
            config_value: cx.new(|cx| InputState::new(window, cx).placeholder("New value")),
            _subscriptions: Vec::new(),
        };
        let chat_prompt = app.chat_prompt.clone();
        app._subscriptions.push(cx.subscribe_in(
            &chat_prompt,
            window,
            |this, _, event, window, cx| {
                if matches!(
                    event,
                    InputEvent::PressEnter {
                        secondary: false,
                        shift: false
                    }
                ) {
                    this.send_prompt("chat", window, cx);
                }
            },
        ));
        let agent_prompt = app.agent_prompt.clone();
        app._subscriptions.push(cx.subscribe_in(
            &agent_prompt,
            window,
            |this, _, event, window, cx| {
                if matches!(
                    event,
                    InputEvent::PressEnter {
                        secondary: false,
                        shift: false
                    }
                ) {
                    this.send_prompt("agent", window, cx);
                }
            },
        ));
        app.start_task_polling(cx);
        app.refresh_bootstrap(cx);
        app
    }

    fn refresh_bootstrap(&mut self, cx: &mut Context<Self>) {
        self.refresh_health(cx);
        self.refresh_config(cx);
        self.refresh_current_page(cx);
    }

    fn switch_page(&mut self, page: Page, cx: &mut Context<Self>) {
        self.current_page = page;
        self.banner = None;
        if self.current_page == Page::Tickets {
            self.start_task_polling(cx);
        } else {
            self.stop_task_polling();
        }
        self.task_modal = None;
        self.config_modal_open = false;
        self.refresh_current_page(cx);
        cx.notify();
    }

    fn toggle_sidebar(&mut self, cx: &mut Context<Self>) {
        self.sidebar_collapsed = !self.sidebar_collapsed;
        cx.notify();
    }

    fn on_action_toggle_sidebar(
        &mut self,
        _: &ToggleSidebar,
        _: &mut Window,
        cx: &mut Context<Self>,
    ) {
        self.toggle_sidebar(cx);
    }

    fn on_action_close_modal(&mut self, _: &CloseModal, _: &mut Window, cx: &mut Context<Self>) {
        if self.task_modal.take().is_some() {
            cx.notify();
        } else if self.config_modal_open {
            self.config_modal_open = false;
            cx.notify();
        }
    }

    fn on_action_clear_conversation(
        &mut self,
        _: &ClearConversation,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        match self.current_page {
            Page::Chat => self.clear_conversation("chat", window, cx),
            Page::Agent => self.clear_conversation("agent", window, cx),
            _ => {}
        }
    }

    fn refresh_current_page(&mut self, cx: &mut Context<Self>) {
        match self.current_page {
            Page::Tickets => {
                self.refresh_repositories(cx);
                self.refresh_tasks(cx);
            }
            Page::Repositories => self.refresh_repositories(cx),
            Page::Chat => self.load_session("chat", cx),
            Page::Agent => self.load_session("agent", cx),
            Page::Research => {}
            Page::Meetings => {
                self.refresh_config(cx);
                self.refresh_meetings(cx);
            }
            Page::Jobs => self.refresh_jobs(cx),
            Page::Integrations => self.refresh_integrations(cx),
            Page::Config => self.refresh_config(cx),
        }
    }

    fn start_task_polling(&mut self, cx: &mut Context<Self>) {
        if self.task_poll_task.is_some() {
            return;
        }

        self.task_poll_task = Some(cx.spawn(async move |this, cx| loop {
            cx.background_executor()
                .timer(TASK_BOARD_REFRESH_INTERVAL)
                .await;
            let should_continue = this
                .update(cx, |state, cx| {
                    if state.current_page != Page::Tickets {
                        return false;
                    }
                    if !state.loading.contains("tasks") {
                        state.refresh_tasks(cx);
                    }
                    true
                })
                .unwrap_or(false);
            if !should_continue {
                break;
            }
        }));
    }

    fn stop_task_polling(&mut self) {
        self.task_poll_task = None;
    }

    fn run_api<T, Request, Apply>(
        &mut self,
        label: impl Into<String>,
        cx: &mut Context<Self>,
        request: Request,
        apply: Apply,
    ) where
        T: Send + 'static,
        Request: FnOnce(ApiClient) -> ApiResult<T> + Send + 'static,
        Apply: FnOnce(&mut Self, ApiResult<T>, &mut Context<Self>) + Send + 'static,
    {
        let label = label.into();
        self.loading.insert(label.clone());
        let client = self.client.clone();
        let task = cx.background_spawn(async move { request(client) });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |state, cx| {
                state.loading.remove(&label);
                apply(state, result, cx);
                cx.notify();
            });
        })
        .detach();
        cx.notify();
    }

    fn set_result_banner<T>(&mut self, result: &ApiResult<T>, success: impl Into<String>) {
        match result {
            Ok(_) => {
                self.banner = Some(Banner {
                    kind: BannerKind::Success,
                    text: success.into(),
                });
            }
            Err(err) => {
                self.banner = Some(Banner {
                    kind: BannerKind::Error,
                    text: err.to_string(),
                });
            }
        }
    }

    fn refresh_health(&mut self, cx: &mut Context<Self>) {
        self.run_api(
            "health",
            cx,
            |client| client.health(),
            |state, result, _| match result {
                Ok(health) => state.health = Some(health),
                Err(err) => {
                    state.health = Some(HealthResponse {
                        status: "offline".to_owned(),
                        profile: None,
                        vault_path: None,
                    });
                    state.banner = Some(Banner {
                        kind: BannerKind::Error,
                        text: format!("Daemon offline: {err}"),
                    });
                }
            },
        );
    }

    fn refresh_config(&mut self, cx: &mut Context<Self>) {
        self.run_api(
            "config",
            cx,
            |client| client.config(),
            |state, result, _| {
                if let Ok(config) = result {
                    state.dictation_status =
                        state.dictation.sync(&config.voice, state.client.clone());
                    state.config = Some(config);
                }
            },
        );
    }

    fn refresh_tasks(&mut self, cx: &mut Context<Self>) {
        self.run_api(
            "tasks",
            cx,
            |client| client.tasks_grouped_by_type(),
            |state, result, _| match result {
                Ok(tasks) => {
                    state.tasks = tasks;
                    state.sync_task_lane_scroll_handles();
                    if state.selected_task().is_none() {
                        state.selected_task_id = state.first_task().map(|task| task.id.clone());
                    }
                }
                Err(err) => state.banner = Some(error_banner(err)),
            },
        );
    }

    fn refresh_repositories(&mut self, cx: &mut Context<Self>) {
        self.run_api(
            "repositories",
            cx,
            |client| {
                let repositories = client.repositories()?;
                let mut worktrees = HashMap::new();
                for repository in &repositories {
                    if let Ok(items) = client.repository_worktrees(&repository.id) {
                        worktrees.insert(repository.id.clone(), items);
                    }
                }
                Ok((repositories, worktrees))
            },
            |state, result, _| match result {
                Ok((repositories, worktrees)) => {
                    state.repositories = repositories;
                    state.worktrees = worktrees;
                    state.repository_list_state.reset(state.repositories.len());
                    let selected_exists = state
                        .selected_repository_id
                        .as_deref()
                        .is_some_and(|id| state.repositories.iter().any(|repo| repo.id == id));
                    if !selected_exists {
                        state.selected_repository_id =
                            state.repositories.first().map(|repo| repo.id.clone());
                    }
                    let task_repository_exists = state
                        .task_repository_id
                        .as_deref()
                        .is_some_and(|id| state.repositories.iter().any(|repo| repo.id == id));
                    if !task_repository_exists {
                        state.task_repository_id =
                            state.repositories.first().map(|repo| repo.id.clone());
                    }
                }
                Err(err) => state.banner = Some(error_banner(err)),
            },
        );
    }

    fn load_session(&mut self, mode: &'static str, cx: &mut Context<Self>) {
        self.run_api(
            format!("{mode}-session"),
            cx,
            move |client| {
                let sessions = client.sessions(mode)?;
                if let Some(session) = sessions.first() {
                    client.get_session(&session.id, SESSION_MESSAGE_LIMIT)
                } else {
                    client.create_session(mode, mode)
                }
            },
            move |state, result, _| match (mode, result) {
                ("chat" | "agent", Ok(session)) => state.apply_session(mode, session),
                (_, Err(err)) => state.banner = Some(error_banner(err)),
                _ => {}
            },
        );
    }

    fn refresh_jobs(&mut self, cx: &mut Context<Self>) {
        self.run_api(
            "jobs",
            cx,
            |client| {
                let jobs = client.jobs()?;
                let workflows = client.workflows().unwrap_or_default();
                let selected = jobs.first().map(|job| job.name.clone());
                let job_runs = selected
                    .as_deref()
                    .map(|name| client.job_runs(name))
                    .transpose()?
                    .unwrap_or_default();
                Ok((jobs, workflows, selected, job_runs))
            },
            |state, result, _| match result {
                Ok((jobs, workflows, selected, runs)) => {
                    state.jobs = jobs;
                    state.workflows = workflows;
                    if state.selected_job_name.is_none() {
                        state.selected_job_name = selected;
                    }
                    state.job_runs = runs;
                    state.job_list_state.reset(state.jobs.len());
                    state.workflow_list_state.reset(state.workflows.len());
                    state.job_run_list_state.reset(state.job_runs.len());
                }
                Err(err) => state.banner = Some(error_banner(err)),
            },
        );
    }

    fn refresh_job_runs(&mut self, job_name: String, cx: &mut Context<Self>) {
        self.selected_job_name = Some(job_name.clone());
        self.run_api(
            "job-runs",
            cx,
            move |client| client.job_runs(&job_name),
            |state, result, _| match result {
                Ok(runs) => {
                    state.job_runs = runs;
                    state.job_run_list_state.reset(state.job_runs.len());
                }
                Err(err) => state.banner = Some(error_banner(err)),
            },
        );
    }

    fn refresh_meetings(&mut self, cx: &mut Context<Self>) {
        self.run_api(
            "meetings",
            cx,
            |client| client.meetings(),
            |state, result, _| match result {
                Ok(meetings) => {
                    state.meetings = meetings;
                    state.meeting_list_state.reset(state.meetings.len());
                    if state.selected_meeting().is_none() {
                        state.selected_meeting_id =
                            state.meetings.first().map(|meeting| meeting.id.clone());
                    }
                }
                Err(err) => state.banner = Some(error_banner(err)),
            },
        );
    }

    fn refresh_integrations(&mut self, cx: &mut Context<Self>) {
        self.run_api(
            "integrations",
            cx,
            |client| client.integrations(),
            |state, result, _| match result {
                Ok(IntegrationsResponse { integrations }) => {
                    state.integrations = integrations;
                    state.integration_list_state.reset(state.integrations.len());
                    if state.selected_integration().is_none() {
                        state.selected_integration_name =
                            state.integrations.first().map(|item| item.name.clone());
                    }
                }
                Err(err) => state.banner = Some(error_banner(err)),
            },
        );
    }

    fn submit_task(&mut self, cx: &mut Context<Self>) {
        let title = value(&self.task_title, cx);
        if title.is_empty() {
            self.banner = Some(Banner {
                kind: BannerKind::Error,
                text: "Task title is required.".to_owned(),
            });
            cx.notify();
            return;
        }
        let request = TaskCreateRequest {
            title,
            description: value(&self.task_description, cx),
            repository_id: self.task_repository_id.clone(),
            task_type: Some(self.task_type.clone()),
            auto_classify: true,
            auto_run: self.task_auto_run,
            auto_run_background: self.task_auto_run,
        };
        self.run_api(
            "create-task",
            cx,
            move |client| client.create_task(request),
            |state, result, cx| match result {
                Ok(task) => {
                    state.selected_task_id = Some(task.id.clone());
                    state.task_modal = None;
                    state.banner = Some(Banner {
                        kind: BannerKind::Success,
                        text: format!("Created task {}.", task.id),
                    });
                    state.refresh_tasks(cx);
                }
                Err(err) => state.banner = Some(error_banner(err)),
            },
        );
    }

    fn submit_repository(&mut self, cx: &mut Context<Self>) {
        let path = value(&self.repository_path, cx);
        if path.is_empty() {
            self.banner = Some(error_text("Repository path is required."));
            cx.notify();
            return;
        }
        let name = non_empty(value(&self.repository_name, cx));
        let request = RepositoryCreateRequest { path, name };
        self.run_api(
            "create-repository",
            cx,
            move |client| client.create_repository(request),
            |state, result, cx| match result {
                Ok(repo) => {
                    state.selected_repository_id = Some(repo.id.clone());
                    state.task_repository_id.get_or_insert(repo.id.clone());
                    state.banner = Some(Banner {
                        kind: BannerKind::Success,
                        text: format!("Registered repository {}.", repo.name),
                    });
                    state.refresh_repositories(cx);
                }
                Err(err) => state.banner = Some(error_banner(err)),
            },
        );
    }

    fn send_prompt(&mut self, mode: &'static str, window: &mut Window, cx: &mut Context<Self>) {
        let label = format!("{mode}-send");
        if self.loading.contains(&label) {
            return;
        }
        let prompt_input = if mode == "chat" {
            self.chat_prompt.clone()
        } else {
            self.agent_prompt.clone()
        };
        let prompt = value(&prompt_input, cx);
        if prompt.is_empty() {
            cx.notify();
            return;
        }
        prompt_input.update(cx, |input, cx| {
            input.set_value("", window, cx);
        });
        self.banner = Some(Banner {
            kind: BannerKind::Info,
            text: format!("Sending {mode} prompt..."),
        });
        let session = if mode == "chat" {
            self.chat_session.clone()
        } else {
            self.agent_session.clone()
        };
        self.run_api(
            label,
            cx,
            move |client| {
                let session = match session {
                    Some(session) => session,
                    None => client.create_session(mode, mode)?,
                };
                client.send_message(&session.id, prompt, SESSION_MESSAGE_LIMIT)
            },
            move |state, result, _| match (mode, result) {
                ("chat", Ok(response)) => state.apply_session("chat", response.session),
                ("agent", Ok(response)) => {
                    state.banner = Some(Banner {
                        kind: BannerKind::Success,
                        text: response.assistant.content.clone(),
                    });
                    state.apply_session("agent", response.session);
                }
                (_, Err(err)) => state.banner = Some(error_banner(err)),
                _ => {}
            },
        );
    }

    fn cancel_session(&mut self, mode: &'static str, cx: &mut Context<Self>) {
        let session = if mode == "chat" {
            self.chat_session.clone()
        } else {
            self.agent_session.clone()
        };
        let Some(session) = session else {
            self.banner = Some(Banner {
                kind: BannerKind::Info,
                text: "No active session.".to_owned(),
            });
            cx.notify();
            return;
        };
        self.run_api(
            format!("{mode}-cancel"),
            cx,
            move |client| client.cancel_session(&session.id),
            |state, result, _| {
                state.set_result_banner(&result, "Cancellation requested.");
            },
        );
    }

    fn run_research(&mut self, cx: &mut Context<Self>) {
        if self.loading.contains("research") {
            return;
        }
        let topic = value(&self.research_topic, cx);
        if topic.is_empty() {
            self.banner = Some(error_text("Research topic is required."));
            cx.notify();
            return;
        }
        let search_mode = self.research_search_mode.clone();
        self.run_api(
            "research",
            cx,
            move |client| client.run_research(topic, search_mode),
            |state, result, _| match result {
                Ok(report) => {
                    state.banner = Some(Banner {
                        kind: BannerKind::Success,
                        text: format!("Research note written to {}.", report.note_path),
                    });
                    state.research_report = Some(report);
                }
                Err(err) => state.banner = Some(error_banner(err)),
            },
        );
    }

    fn start_recording(&mut self, cx: &mut Context<Self>) {
        let title = value(&self.meeting_title, cx);
        if title.is_empty() {
            self.banner = Some(error_text("Meeting title is required."));
            cx.notify();
            return;
        }
        let source = Some(self.meeting_source.clone());
        self.run_api(
            "record-meeting",
            cx,
            move |client| client.record_meeting(title, source),
            |state, result, cx| match result {
                Ok(meeting) => {
                    state.selected_meeting_id = Some(meeting.id.clone());
                    state.banner = Some(Banner {
                        kind: BannerKind::Success,
                        text: format!("Recording {}.", meeting.title),
                    });
                    state.refresh_meetings(cx);
                }
                Err(err) => state.banner = Some(error_banner(err)),
            },
        );
    }

    fn save_config(&mut self, cx: &mut Context<Self>) {
        let field = self.selected_config_key;
        let raw = value(&self.config_value, cx);
        self.save_config_value(field, raw, true, cx);
    }

    fn save_config_value(
        &mut self,
        field_key: &'static str,
        raw: String,
        close_modal: bool,
        cx: &mut Context<Self>,
    ) {
        let Some(field) = config_field(field_key) else {
            self.banner = Some(error_text(format!("Unsupported config field: {field_key}")));
            cx.notify();
            return;
        };
        if raw.is_empty() && !field.allows_empty() {
            self.banner = Some(error_text("Enter a new config value first."));
            cx.notify();
            return;
        }
        let patch = match build_config_patch(field.key, &raw) {
            Ok(patch) => patch,
            Err(message) => {
                self.banner = Some(error_text(message));
                cx.notify();
                return;
            }
        };
        self.run_api(
            "save-config",
            cx,
            move |client| client.update_config(patch),
            move |state, result, _| match result {
                Ok(ConfigUpdateResponse {
                    config,
                    restart_required,
                    ..
                }) => {
                    state.config = Some(config);
                    if close_modal {
                        state.config_modal_open = false;
                    }
                    state.banner = Some(Banner {
                        kind: if restart_required {
                            BannerKind::Info
                        } else {
                            BannerKind::Success
                        },
                        text: if restart_required {
                            "Config saved. Restart the daemon to apply this change.".to_owned()
                        } else {
                            "Config saved.".to_owned()
                        },
                    });
                }
                Err(err) => state.banner = Some(error_banner(err)),
            },
        );
    }

    fn clear_conversation(
        &mut self,
        mode: &'static str,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        if self.loading.contains(&format!("{mode}-send")) {
            self.banner = Some(Banner {
                kind: BannerKind::Info,
                text: format!("Wait for the current {mode} response before clearing."),
            });
            cx.notify();
            return;
        }

        let label = format!("{mode}-clear");
        if self.loading.contains(&label) {
            return;
        }

        let input = if mode == "chat" {
            self.chat_prompt.clone()
        } else {
            self.agent_prompt.clone()
        };
        input.update(cx, |input, cx| {
            input.set_value("", window, cx);
        });

        self.clear_session_state(mode);
        self.banner = Some(Banner {
            kind: BannerKind::Info,
            text: format!("Cleared {mode}. Starting a fresh session."),
        });

        self.run_api(
            label,
            cx,
            move |client| client.create_session(mode, mode),
            move |state, result, _| match (mode, result) {
                ("chat", Ok(session)) => {
                    state.apply_session("chat", session);
                    state.banner = Some(Banner {
                        kind: BannerKind::Success,
                        text: "Chat cleared.".to_owned(),
                    });
                }
                ("agent", Ok(session)) => {
                    state.apply_session("agent", session);
                    state.banner = Some(Banner {
                        kind: BannerKind::Success,
                        text: "Agent chat cleared.".to_owned(),
                    });
                }
                (_, Err(err)) => state.banner = Some(error_banner(err)),
                _ => {}
            },
        );
    }

    fn sync_task_lane_scroll_handles(&mut self) {
        let task_types: HashSet<String> = kanban_task_types(&self.tasks).into_iter().collect();
        self.task_lane_scroll_handles
            .retain(|task_type, _| task_types.contains(task_type));
        for task_type in task_types {
            self.task_lane_scroll_handles.entry(task_type).or_default();
        }
    }

    fn apply_session(&mut self, mode: &'static str, session: SessionRecord) {
        let message_count = session.messages.len();
        match mode {
            "chat" => {
                self.chat_message_cache.sync(&session);
                self.chat_list_state.reset(message_count);
                self.chat_list_state.scroll_to_end();
                self.chat_session = Some(session);
            }
            "agent" => {
                self.agent_message_cache.sync(&session);
                self.agent_list_state.reset(message_count);
                self.agent_list_state.scroll_to_end();
                self.agent_session = Some(session);
            }
            _ => {}
        }
    }

    fn clear_session_state(&mut self, mode: &'static str) {
        match mode {
            "chat" => {
                self.chat_session = None;
                self.chat_message_cache.clear();
                self.chat_list_state.reset(0);
            }
            "agent" => {
                self.agent_session = None;
                self.agent_message_cache.clear();
                self.agent_list_state.reset(0);
            }
            _ => {}
        }
    }

    fn message_cache(&self, mode: &'static str) -> &MessageRenderCache {
        if mode == "chat" {
            &self.chat_message_cache
        } else {
            &self.agent_message_cache
        }
    }

    fn conversation_list_state(&self, mode: &'static str) -> ListState {
        if mode == "chat" {
            self.chat_list_state.clone()
        } else {
            self.agent_list_state.clone()
        }
    }

    fn selected_task(&self) -> Option<&Ticket> {
        self.selected_task_id
            .as_deref()
            .and_then(|id| self.tasks.values().flatten().find(|task| task.id == id))
    }

    fn first_task(&self) -> Option<&Ticket> {
        ordered_task_types(&self.tasks)
            .into_iter()
            .find_map(|task_type| self.tasks.get(&task_type).and_then(|tasks| tasks.first()))
    }

    fn selected_repository(&self) -> Option<&Repository> {
        self.selected_repository_id
            .as_deref()
            .and_then(|id| self.repositories.iter().find(|repo| repo.id == id))
    }

    fn selected_job(&self) -> Option<&Job> {
        self.selected_job_name
            .as_deref()
            .and_then(|name| self.jobs.iter().find(|job| job.name == name))
    }

    fn selected_meeting(&self) -> Option<&Meeting> {
        self.selected_meeting_id
            .as_deref()
            .and_then(|id| self.meetings.iter().find(|meeting| meeting.id == id))
    }

    fn selected_integration(&self) -> Option<&IntegrationRecord> {
        self.selected_integration_name
            .as_deref()
            .and_then(|name| self.integrations.iter().find(|item| item.name == name))
    }

    fn select_integration(&mut self, name: String, window: &mut Window, cx: &mut Context<Self>) {
        if self.selected_integration_name.as_deref() != Some(name.as_str()) {
            self.selected_integration_name = Some(name);
            self.clear_integration_inputs(window, cx);
        }
        cx.notify();
    }

    fn clear_integration_inputs(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        for input in [
            self.integration_base_url.clone(),
            self.integration_email.clone(),
            self.integration_api_token.clone(),
            self.integration_bot_token.clone(),
            self.integration_access_token.clone(),
        ] {
            input.update(cx, |input, cx| input.set_value("", window, cx));
        }
    }

    fn credential_input(&self, field_name: &str) -> Option<Entity<InputState>> {
        match field_name {
            "base_url" => Some(self.integration_base_url.clone()),
            "email" => Some(self.integration_email.clone()),
            "api_token" => Some(self.integration_api_token.clone()),
            "bot_token" => Some(self.integration_bot_token.clone()),
            "access_token" => Some(self.integration_access_token.clone()),
            _ => None,
        }
    }

    fn integration_credentials_payload(
        &self,
        fields: &[IntegrationCredentialField],
        cx: &mut Context<Self>,
    ) -> BTreeMap<String, String> {
        let mut credentials = BTreeMap::new();
        for field in fields {
            if let Some(input) = self.credential_input(&field.name) {
                let field_value = value(&input, cx);
                if !field_value.is_empty() {
                    credentials.insert(field.name.clone(), field_value);
                }
            }
        }
        credentials
    }

    fn save_integration_credentials(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        let Some(integration) = self
            .selected_integration()
            .or_else(|| self.integrations.first())
            .cloned()
        else {
            self.banner = Some(error_text("Select an integration first."));
            cx.notify();
            return;
        };
        let credentials = self.integration_credentials_payload(&integration.credential_fields, cx);
        if credentials.is_empty() {
            self.banner = Some(error_text("Enter at least one credential value."));
            cx.notify();
            return;
        }
        self.clear_integration_inputs(window, cx);
        let name = integration.name.clone();
        let label = format!("save-integration-{name}");
        let request = IntegrationCredentialsUpdate {
            credentials,
            merge: true,
        };
        self.run_api(
            label,
            cx,
            move |client| client.save_integration_credentials(&name, request),
            |state, result, cx| {
                state.set_result_banner(&result, "Saved integration credentials.");
                if result.is_ok() {
                    state.refresh_integrations(cx);
                }
            },
        );
    }

    fn clear_integration_credentials(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        let Some(name) = self
            .selected_integration_name
            .clone()
            .or_else(|| self.integrations.first().map(|item| item.name.clone()))
        else {
            self.banner = Some(error_text("Select an integration first."));
            cx.notify();
            return;
        };
        self.clear_integration_inputs(window, cx);
        let label = format!("clear-integration-{name}");
        self.run_api(
            label,
            cx,
            move |client| client.clear_integration_credentials(&name),
            |state, result, cx| {
                state.set_result_banner(&result, "Cleared integration credentials.");
                if result.is_ok() {
                    state.refresh_integrations(cx);
                }
            },
        );
    }

    fn selected_config_field(&self) -> &'static ConfigField {
        config_field(self.selected_config_key).unwrap_or(&CONFIG_FIELDS[0])
    }

    fn open_config_field(
        &mut self,
        key: &'static str,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        self.selected_config_key = key;
        self.sync_config_input(window, cx);
        self.config_modal_open = true;
        cx.notify();
    }

    fn sync_config_input(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        let Some(config) = &self.config else {
            return;
        };
        if config_field(self.selected_config_key).is_none() {
            self.selected_config_key = CONFIG_FIELDS[0].key;
            self.config_value_source = None;
        }
        let key = self.selected_config_key;
        let current = config_value(config, key);
        let should_sync = self
            .config_value_source
            .as_ref()
            .map(|(source_key, source_value)| *source_key != key || source_value != &current)
            .unwrap_or(true);
        if should_sync {
            self.config_value.update(cx, |input, cx| {
                input.set_value(current.clone(), window, cx);
            });
            self.config_value_source = Some((key, current));
        }
    }
}

impl Render for NinaDesktop {
    fn render(&mut self, window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let page = self.render_page(window, cx);
        let page_frame = match self.current_page {
            Page::Tickets
            | Page::Repositories
            | Page::Chat
            | Page::Agent
            | Page::Meetings
            | Page::Jobs
            | Page::Integrations
            | Page::Config => ui::page_workspace_frame(page),
            _ => ui::page_scroll_frame(page),
        };
        ui::app_root()
            .id("nina-desktop-root")
            .track_focus(&self.focus_handle)
            .key_context(DESKTOP_CONTEXT)
            .on_action(cx.listener(Self::on_action_toggle_sidebar))
            .on_action(cx.listener(Self::on_action_close_modal))
            .on_action(cx.listener(Self::on_action_clear_conversation))
            .child(
                h_flex().size_full().child(self.render_sidebar(cx)).child(
                    v_flex()
                        .flex_1()
                        .h_full()
                        .overflow_hidden()
                        .child(self.render_header(window, cx))
                        .child(self.render_status_bar())
                        .child(page_frame),
                ),
            )
            .child(self.render_task_modal(cx))
            .child(self.render_config_modal(cx))
    }
}

impl NinaDesktop {
    fn render_sidebar(&self, cx: &mut Context<Self>) -> Div {
        let toggle_icon = if self.sidebar_collapsed {
            IconName::PanelLeftOpen
        } else {
            IconName::PanelLeftClose
        };
        let app = cx.entity().downgrade();
        let sidebar = ui::sidebar_shell(self.sidebar_collapsed).child(
            ui::sidebar_brand(self.sidebar_collapsed, toggle_icon)
                .id("sidebar-brand-toggle")
                .on_click(move |_, _, cx| {
                    let _ = app.update(cx, |state, cx| state.toggle_sidebar(cx));
                }),
        );

        let mut nav = v_flex().gap_1();
        for page in Page::ALL {
            let selected = self.current_page == page;
            let app = cx.entity().downgrade();
            nav = nav.child(
                ui::sidebar_item(
                    page.label(),
                    page.description(),
                    page.icon(),
                    selected,
                    self.sidebar_collapsed,
                )
                .id(format!("nav-{}", page.label()))
                .on_click(move |_, _, cx| {
                    let _ = app.update(cx, |state, cx| state.switch_page(page, cx));
                }),
            );
        }
        let footer = if self.sidebar_collapsed {
            div()
                .flex()
                .justify_center()
                .child(
                    div()
                        .size(px(8.))
                        .rounded_full()
                        .bg(if self.client.has_token() {
                            rgb(0x22c55e)
                        } else {
                            rgb(0xf97316)
                        }),
                )
        } else {
            v_flex()
                .gap_1()
                .p_2()
                .rounded(px(8.))
                .bg(color::surface())
                .border_1()
                .border_color(color::border())
                .child(small_text("Daemon"))
                .child(small_text(format!(
                    "{}{}",
                    self.client.base_url(),
                    if self.client.has_token() {
                        ""
                    } else {
                        " (no token)"
                    }
                )))
        };

        sidebar.child(ui::sidebar_scroll_frame(
            v_flex().gap_3().child(nav).child(footer),
        ))
    }

    fn render_header(&self, _window: &mut Window, _cx: &mut Context<Self>) -> Div {
        h_flex()
            .px_5()
            .py_4()
            .justify_between()
            .border_b_1()
            .border_color(color::border())
            .child(
                v_flex()
                    .gap_1()
                    .child(
                        div()
                            .text_2xl()
                            .font_weight(FontWeight::BOLD)
                            .child(self.current_page.label()),
                    )
                    .child(small_text(self.current_page.description())),
            )
            .child(self.render_health_chip())
    }

    fn render_status_bar(&self) -> Div {
        let Some(banner) = &self.banner else {
            return div().h(px(0.));
        };
        let color = match banner.kind {
            BannerKind::Info => rgb(0x38bdf8),
            BannerKind::Success => rgb(0x22c55e),
            BannerKind::Error => rgb(0xef4444),
        };
        div()
            .mx_4()
            .mt_3()
            .p_3()
            .rounded(px(8.))
            .border_1()
            .border_color(color)
            .bg(color::surface())
            .child(banner.text.clone())
    }

    fn render_health_chip(&self) -> Div {
        let (status, detail, color) = match &self.health {
            Some(health) if health.status == "ok" => (
                "Online".to_owned(),
                health
                    .profile
                    .clone()
                    .unwrap_or_else(|| "default".to_owned()),
                rgb(0x22c55e),
            ),
            Some(health) => (health.status.clone(), "daemon".to_owned(), rgb(0xf97316)),
            None => ("Checking".to_owned(), "daemon".to_owned(), rgb(0x94a3b8)),
        };
        h_flex()
            .gap_2()
            .px_3()
            .py_2()
            .rounded(px(8.))
            .border_1()
            .border_color(color)
            .bg(color::surface())
            .child(div().size_2().rounded_full().bg(color))
            .child(format!("{status} - {detail}"))
    }

    fn render_page(&mut self, window: &mut Window, cx: &mut Context<Self>) -> Div {
        match self.current_page {
            Page::Tickets => self.render_tickets_page(cx),
            Page::Repositories => self.render_repositories_page(cx),
            Page::Chat => self.render_conversation_page("chat", cx),
            Page::Agent => self.render_conversation_page("agent", cx),
            Page::Research => self.render_research_page(cx),
            Page::Meetings => self.render_meetings_page(cx),
            Page::Jobs => self.render_jobs_page(cx),
            Page::Integrations => self.render_integrations_page(cx),
            Page::Config => self.render_config_page(window, cx),
        }
    }

    fn render_tickets_page(&mut self, cx: &mut Context<Self>) -> Div {
        let mut lanes = h_flex().h_full().min_h(px(0.)).items_stretch().gap_3();
        for task_type in kanban_task_types(&self.tasks) {
            let task_count = self.tasks.get(&task_type).map(Vec::len).unwrap_or(0);
            let accent = task_color(&task_type);
            let lane_body = if task_count == 0 {
                div()
                    .size_full()
                    .child(
                        div()
                            .p_3()
                            .rounded(px(8.))
                            .border_1()
                            .border_color(color::border())
                            .bg(color::surface())
                            .child(small_text("No tasks")),
                    )
                    .into_any_element()
            } else {
                let lane_key = task_type.clone();
                let list_id = format!("task-list-{task_type}");
                let scroll_handle = self
                    .task_lane_scroll_handles
                    .get(&task_type)
                    .cloned()
                    .unwrap_or_else(UniformListScrollHandle::new);
                div()
                    .size_full()
                    .min_h(px(0.))
                    .child(
                        uniform_list(
                            list_id,
                            task_count,
                            cx.processor(move |this, range: Range<usize>, _window, cx| {
                                let mut items = Vec::with_capacity(range.end - range.start);
                                if let Some(tasks) = this.tasks.get(&lane_key) {
                                    for ix in range {
                                        if let Some(task) = tasks.get(ix) {
                                            items.push(this.render_task_card(task, accent, cx));
                                        }
                                    }
                                }
                                items
                            }),
                        )
                        .track_scroll(&scroll_handle)
                        .size_full()
                        .pr_1(),
                    )
                    .into_any_element()
            };
            lanes = lanes.child(ui::kanban_virtual_lane(
                task_type.clone(),
                task_count,
                accent,
                lane_body,
            ));
        }

        let total_tasks: usize = self.tasks.values().map(Vec::len).sum();
        let selected_text = self
            .selected_task()
            .map(|task| task.title.clone())
            .unwrap_or_else(|| "No task selected".to_owned());
        let app_create = cx.entity().downgrade();
        let app_detail = cx.entity().downgrade();
        let toolbar = h_flex()
            .justify_between()
            .gap_3()
            .child(
                h_flex()
                    .gap_2()
                    .flex_wrap()
                    .child(status_pill(format!("{total_tasks} tasks"), color::accent()))
                    .child(status_pill(selected_text, rgb(0x64748b))),
            )
            .child(
                h_flex()
                    .gap_2()
                    .child(
                        Button::new("open-task-detail")
                            .small()
                            .label("Detail")
                            .on_click(move |_, _, cx| {
                                let _ = app_detail.update(cx, |state, cx| {
                                    if state.selected_task().is_none() {
                                        state.selected_task_id =
                                            state.first_task().map(|task| task.id.clone());
                                    }
                                    state.task_modal = Some(TaskModal::Detail);
                                    cx.notify();
                                });
                            }),
                    )
                    .child(
                        Button::new("open-create-task")
                            .primary()
                            .small()
                            .icon(IconName::Plus)
                            .label("New Task")
                            .on_click(move |_, _, cx| {
                                let _ = app_create.update(cx, |state, cx| {
                                    state.task_modal = Some(TaskModal::Create);
                                    cx.notify();
                                });
                            }),
                    ),
            );
        ui::task_workspace()
            .child(ui::task_board_surface(
                v_flex()
                    .flex_1()
                    .min_h(px(0.))
                    .gap_3()
                    .child(toolbar)
                    .child(ui::task_board_scroll(lanes)),
            ))
            .child(if self.loading.contains("tasks") {
                loading_panel("Loading tasks...")
            } else {
                div()
            })
    }

    fn render_task_card(
        &self,
        task: &Ticket,
        accent: Rgba,
        cx: &mut Context<Self>,
    ) -> Stateful<Div> {
        let task_id = task.id.clone();
        let repo_name = task
            .repository_name
            .clone()
            .unwrap_or_else(|| "no repo".to_owned());
        let meta = format!(
            "{} - {}{}",
            task.status,
            repo_name,
            if task.classification_reason.is_some() {
                " - classified"
            } else {
                ""
            }
        );
        let selected = self.selected_task_id.as_deref() == Some(task.id.as_str());
        let app = cx.entity().downgrade();
        ui::kanban_card(selected, accent)
            .id(format!("task-row-{}", task.id))
            .on_click(move |_, _, cx| {
                let _ = app.update(cx, |state, cx| {
                    state.selected_task_id = Some(task_id.clone());
                    state.task_modal = Some(TaskModal::Detail);
                    cx.notify();
                });
            })
            .child(
                h_flex()
                    .justify_between()
                    .gap_2()
                    .child(
                        div()
                            .flex_1()
                            .overflow_hidden()
                            .child(ui::row_title(task.title.clone())),
                    )
                    .child(status_pill(task.status.clone(), accent)),
            )
            .child(ui::row_meta(meta))
            .child(ui::row_meta(format!("Updated {}", task.updated_at)))
    }

    fn render_task_modal(&self, cx: &mut Context<Self>) -> Div {
        if self.current_page != Page::Tickets {
            return div();
        }
        let Some(modal) = self.task_modal else {
            return div();
        };
        let close_app = cx.entity().downgrade();
        let close = Button::new("close-task-modal")
            .small()
            .label("Close")
            .on_click(move |_, _, cx| {
                let _ = close_app.update(cx, |state, cx| {
                    state.task_modal = None;
                    cx.notify();
                });
            });
        let (title, body) = match modal {
            TaskModal::Create => ("Create Task", self.render_task_create_body(cx)),
            TaskModal::Detail => ("Task Detail", self.render_task_detail_body(cx)),
        };

        let backdrop_app = cx.entity().downgrade();
        let modal_window = ui::modal_window(
            v_flex()
                .child(ui::modal_header(title, close))
                .child(ui::modal_body(body)),
        )
        .on_mouse_down(MouseButton::Left, |_, _, cx| {
            cx.stop_propagation();
        });

        ui::modal_overlay(modal_window).on_mouse_down(MouseButton::Left, move |_, _, cx| {
            let _ = backdrop_app.update(cx, |state, cx| {
                state.task_modal = None;
                cx.notify();
            });
        })
    }

    fn render_config_modal(&self, cx: &mut Context<Self>) -> Div {
        if self.current_page != Page::Config || !self.config_modal_open {
            return div();
        }
        let Some(config) = &self.config else {
            return div();
        };

        let selected = self.selected_config_field();
        let close_app = cx.entity().downgrade();
        let close = Button::new("close-config-modal")
            .small()
            .label("Close")
            .on_click(move |_, _, cx| {
                let _ = close_app.update(cx, |state, cx| {
                    state.config_modal_open = false;
                    cx.notify();
                });
            });

        let backdrop_app = cx.entity().downgrade();
        let modal_window = ui::modal_window(
            v_flex()
                .child(ui::modal_header(format!("Edit {}", selected.label), close))
                .child(ui::modal_body(self.render_config_editor_body(config, cx))),
        )
        .on_mouse_down(MouseButton::Left, |_, _, cx| {
            cx.stop_propagation();
        });

        ui::modal_overlay(modal_window).on_mouse_down(MouseButton::Left, move |_, _, cx| {
            let _ = backdrop_app.update(cx, |state, cx| {
                state.config_modal_open = false;
                cx.notify();
            });
        })
    }

    fn render_config_editor_body(&self, config: &ConfigSnapshot, cx: &mut Context<Self>) -> Div {
        let selected = self.selected_config_field();
        let current = config_value(config, selected.key);
        let editor_color = config_editor_color(selected.editor);
        let mut editor = v_flex()
            .gap_4()
            .child(
                v_flex()
                    .gap_2()
                    .child(
                        h_flex()
                            .gap_2()
                            .flex_wrap()
                            .child(status_pill(selected.editor.label(), editor_color))
                            .child(if selected.restart_required {
                                status_pill("restart", rgb(0xf97316))
                            } else {
                                div()
                            }),
                    )
                    .child(small_text(selected.description)),
            )
            .child(
                v_flex()
                    .gap_2()
                    .child(ui::kv_row("Key", selected.key))
                    .child(ui::kv_row("Current", current.clone())),
            );

        if let Some(options) = selected.editor.options() {
            let mut choices = h_flex().gap_2().flex_wrap();
            for option in options {
                let app = cx.entity().downgrade();
                let option_value = (*option).to_owned();
                let button_id = format!("config-option-{}-{}", selected.key, option);
                let mut button = Button::new(button_id).small().label(*option);
                if config_option_matches(&current, option) {
                    button = button.primary();
                } else {
                    button = button.ghost();
                }
                let key = selected.key;
                choices = choices.child(button.on_click(move |_, _, cx| {
                    let _ = app.update(cx, |state, cx| {
                        state.selected_config_key = key;
                        state.save_config_value(key, option_value.clone(), true, cx);
                    });
                }));
            }
            editor = editor.child(label("Options")).child(choices);
        } else {
            let app = cx.entity().downgrade();
            editor = editor
                .child(label("Value"))
                .child(Input::new(&self.config_value).cleanable(true))
                .child(
                    Button::new("save-config")
                        .primary()
                        .small()
                        .label("Save")
                        .on_click(move |_, _, cx| {
                            let _ = app.update(cx, |state, cx| state.save_config(cx));
                        }),
                );
        }

        editor
    }

    fn render_task_create_body(&self, cx: &mut Context<Self>) -> Div {
        let app = cx.entity().downgrade();
        let mut type_buttons = h_flex().gap_1().flex_wrap();
        for task_type in TASK_TYPE_ORDER {
            let task_type_value = (*task_type).to_owned();
            let selected = self.task_type == *task_type;
            let app = cx.entity().downgrade();
            type_buttons = type_buttons.child(
                Button::new(format!("task-type-{task_type}"))
                    .xsmall()
                    .selected(selected)
                    .label(*task_type)
                    .on_click(move |_, _, cx| {
                        let _ = app.update(cx, |state, cx| {
                            state.task_type = task_type_value.clone();
                            cx.notify();
                        });
                    }),
            );
        }

        let mut repo_buttons = h_flex().gap_1().flex_wrap();
        for repo in &self.repositories {
            let repo_id = repo.id.clone();
            let selected = self.task_repository_id.as_deref() == Some(repo.id.as_str());
            let app = cx.entity().downgrade();
            repo_buttons = repo_buttons.child(
                Button::new(format!("task-repo-{}", repo.id))
                    .xsmall()
                    .selected(selected)
                    .label(repo.name.clone())
                    .on_click(move |_, _, cx| {
                        let _ = app.update(cx, |state, cx| {
                            state.task_repository_id = Some(repo_id.clone());
                            cx.notify();
                        });
                    }),
            );
        }
        let app_auto = cx.entity().downgrade();
        let close_app = cx.entity().downgrade();
        v_flex()
            .gap_3()
            .child(Input::new(&self.task_title))
            .child(Input::new(&self.task_description))
            .child(label("Type"))
            .child(type_buttons)
            .child(label("Repository"))
            .child(
                repo_buttons.child(
                    Button::new("task-repo-none")
                        .xsmall()
                        .label("No repo")
                        .on_click(move |_, _, cx| {
                            let _ = app_auto.update(cx, |state, cx| {
                                state.task_repository_id = None;
                                cx.notify();
                            });
                        }),
                ),
            )
            .child(
                h_flex()
                    .justify_between()
                    .gap_2()
                    .flex_wrap()
                    .child(
                        Button::new("task-auto-run")
                            .small()
                            .selected(self.task_auto_run)
                            .label("Auto-run")
                            .on_click({
                                let app = cx.entity().downgrade();
                                move |_, _, cx| {
                                    let _ = app.update(cx, |state, cx| {
                                        state.task_auto_run = !state.task_auto_run;
                                        cx.notify();
                                    });
                                }
                            }),
                    )
                    .child(
                        h_flex()
                            .gap_2()
                            .child(
                                Button::new("cancel-create-task")
                                    .small()
                                    .label("Cancel")
                                    .on_click(move |_, _, cx| {
                                        let _ = close_app.update(cx, |state, cx| {
                                            state.task_modal = None;
                                            cx.notify();
                                        });
                                    }),
                            )
                            .child(
                                Button::new("create-task")
                                    .primary()
                                    .small()
                                    .icon(IconName::Plus)
                                    .label("Create")
                                    .on_click(move |_, _, cx| {
                                        let _ = app.update(cx, |state, cx| state.submit_task(cx));
                                    }),
                            ),
                    ),
            )
    }

    fn render_task_detail_body(&self, cx: &mut Context<Self>) -> Div {
        let Some(task) = self.selected_task() else {
            return ui::empty_state(
                IconName::Inbox,
                "No task selected",
                "Select a task from the board to inspect and update it.",
            );
        };
        let task_id = task.id.clone();
        let task_note_path = task.note_path.clone();
        let selected_repo = task
            .repository_name
            .clone()
            .unwrap_or_else(|| "No repository".to_owned());
        let mut type_buttons = h_flex().gap_1().flex_wrap();
        for task_type in TASK_TYPE_ORDER {
            let new_type = (*task_type).to_owned();
            let task_id = task_id.clone();
            let app = cx.entity().downgrade();
            type_buttons = type_buttons.child(
                Button::new(format!("set-{}-{task_type}", task.id))
                    .xsmall()
                    .selected(task.task_type == *task_type)
                    .label(*task_type)
                    .on_click(move |_, _, cx| {
                        let _ = app.update(cx, |state, cx| {
                            let request = TaskUpdateRequest {
                                task_type: Some(new_type.clone()),
                                ..TaskUpdateRequest::default()
                            };
                            state.run_api(
                                "patch-task-type",
                                cx,
                                {
                                    let task_id = task_id.clone();
                                    move |client| client.patch_task(&task_id, request)
                                },
                                |state, result, cx| {
                                    state.set_result_banner(&result, "Task type updated.");
                                    state.refresh_tasks(cx);
                                },
                            );
                        });
                    }),
            );
        }

        let mut repo_buttons = h_flex().gap_1().flex_wrap();
        for repo in &self.repositories {
            let repo_id = repo.id.clone();
            let task_id = task.id.clone();
            let app = cx.entity().downgrade();
            repo_buttons = repo_buttons.child(
                Button::new(format!("set-repo-{}-{}", task.id, repo.id))
                    .xsmall()
                    .selected(task.repository_id.as_deref() == Some(repo.id.as_str()))
                    .label(repo.name.clone())
                    .on_click(move |_, _, cx| {
                        let _ = app.update(cx, |state, cx| {
                            let request = TaskUpdateRequest {
                                repository_id: Some(Some(repo_id.clone())),
                                ..TaskUpdateRequest::default()
                            };
                            state.run_api(
                                "patch-task-repo",
                                cx,
                                {
                                    let task_id = task_id.clone();
                                    move |client| client.patch_task(&task_id, request)
                                },
                                |state, result, cx| {
                                    state.set_result_banner(&result, "Repository updated.");
                                    state.refresh_tasks(cx);
                                },
                            );
                        });
                    }),
            );
        }

        let classify_id = task.id.clone();
        let run_id = task.id.clone();
        let archive_id = task.id.clone();
        let delete_id = task.id.clone();
        let logs_id = task.id.clone();
        let open_app = cx.entity().downgrade();
        let mut body = v_flex()
            .gap_3()
            .child(
                div()
                    .font_weight(FontWeight::BOLD)
                    .child(task.title.clone()),
            )
            .child(small_text(format!(
                "{} - {} - {}",
                task.id, task.status, selected_repo
            )))
            .child(small_text(task.description.clone()))
            .child(label("Type"))
            .child(type_buttons)
            .child(label("Repository"))
            .child(repo_buttons)
            .child(label("Automation"))
            .child(
                h_flex()
                    .gap_2()
                    .flex_wrap()
                    .child(
                        Button::new("task-classify")
                            .small()
                            .label("Classify")
                            .on_click({
                                let app = cx.entity().downgrade();
                                move |_, _, cx| {
                                    let _ = app.update(cx, |state, cx| {
                                        let classify_id = classify_id.clone();
                                        state.run_api(
                                            "classify-task",
                                            cx,
                                            move |client| client.classify_task(&classify_id),
                                            |state, result, cx| {
                                                state.set_result_banner(
                                                    &result,
                                                    "Classifier run complete.",
                                                );
                                                state.refresh_tasks(cx);
                                            },
                                        );
                                    });
                                }
                            }),
                    )
                    .child(Button::new("task-run").small().label("Run").on_click({
                        let app = cx.entity().downgrade();
                        move |_, _, cx| {
                            let _ = app.update(cx, |state, cx| {
                                let run_id = run_id.clone();
                                state.run_api(
                                    "run-task",
                                    cx,
                                    move |client| client.run_task(&run_id),
                                    |state, result, cx| {
                                        state.set_result_banner(&result, "Task run queued.");
                                        state.refresh_tasks(cx);
                                    },
                                );
                            });
                        }
                    }))
                    .child(self.render_open_note_button(
                        "task-open-note".to_owned(),
                        "Open Note",
                        task_note_path,
                        "Task has no note yet.",
                        "Opened the task note.",
                        cx,
                    ))
                    .child(Button::new("task-logs").small().label("Logs").on_click(
                        move |_, _, cx| {
                            let _ = open_app.update(cx, |state, cx| {
                                let logs_id = logs_id.clone();
                                state.run_api(
                                    "task-logs",
                                    cx,
                                    move |client| client.task_logs(&logs_id, 200),
                                    |state, result, _| match result {
                                        Ok(logs) => state.task_logs = Some(logs),
                                        Err(err) => state.banner = Some(error_banner(err)),
                                    },
                                );
                            });
                        },
                    ))
                    .child(
                        Button::new("task-archive")
                            .small()
                            .label("Archive")
                            .on_click({
                                let app = cx.entity().downgrade();
                                move |_, _, cx| {
                                    let _ = app.update(cx, |state, cx| {
                                        let archive_id = archive_id.clone();
                                        state.run_api(
                                            "archive-task",
                                            cx,
                                            move |client| client.archive_task(&archive_id),
                                            |state, result, cx| {
                                                state.set_result_banner(&result, "Task archived.");
                                                state.task_modal = None;
                                                state.refresh_tasks(cx);
                                            },
                                        );
                                    });
                                }
                            }),
                    )
                    .child(
                        Button::new("task-delete")
                            .small()
                            .danger()
                            .label("Delete")
                            .on_click({
                                let app = cx.entity().downgrade();
                                move |_, _, cx| {
                                    let _ = app.update(cx, |state, cx| {
                                        let delete_id = delete_id.clone();
                                        state.run_api(
                                            "delete-task",
                                            cx,
                                            move |client| client.delete_task(&delete_id),
                                            |state, result, cx| {
                                                state.set_result_banner(&result, "Task deleted.");
                                                state.selected_task_id = None;
                                                state.task_modal = None;
                                                state.refresh_tasks(cx);
                                            },
                                        );
                                    });
                                }
                            }),
                    ),
            );
        if let Some(logs) = &self.task_logs {
            body = body.child(render_task_logs(logs));
        }
        body
    }

    fn render_repository_row(&self, repo: &Repository, cx: &mut Context<Self>) -> AnyElement {
        let repo_id = repo.id.clone();
        let select_id = repo.id.clone();
        let delete_id = repo.id.clone();
        let selected = self.selected_repository_id.as_deref() == Some(repo.id.as_str());
        let task_default = self.task_repository_id.as_deref() == Some(repo.id.as_str());
        let repo_worktrees = self.worktrees.get(&repo.id).cloned().unwrap_or_default();
        let worktree_count = repo_worktrees.len();
        let worktree_count_label = if worktree_count == 1 {
            "1 worktree".to_owned()
        } else {
            format!("{worktree_count} worktrees")
        };
        let mut worktree_list = v_flex().gap_2();
        for worktree in repo_worktrees {
            let branch = worktree.branch.unwrap_or_else(|| "detached".to_owned());
            worktree_list = worktree_list.child(
                ui::compact_row(false, rgb(0x64748b))
                    .cursor_default()
                    .child(ui::icon_badge(IconName::Network, rgb(0x64748b)))
                    .child(
                        v_flex()
                            .flex_1()
                            .min_w(px(0.))
                            .overflow_hidden()
                            .gap_1()
                            .child(ui::row_title(branch))
                            .child(ui::row_meta(format!(
                                "{}{}{}",
                                worktree.path,
                                if worktree.bare { " - bare" } else { "" },
                                worktree
                                    .locked
                                    .map(|lock| format!(" - locked: {lock}"))
                                    .unwrap_or_default()
                            ))),
                    ),
            );
        }
        if worktree_count == 0 {
            worktree_list = worktree_list.child(ui::row_meta("No worktrees reported."));
        }
        ui::surface_block()
            .child(
                ui::compact_row(selected, rgb(0x38bdf8))
                    .id(format!("repo-row-{}", repo.id))
                    .on_click({
                        let app = cx.entity().downgrade();
                        move |_, _, cx| {
                            let _ = app.update(cx, |state, cx| {
                                state.selected_repository_id = Some(select_id.clone());
                                cx.notify();
                            });
                        }
                    })
                    .child(ui::icon_badge(IconName::FolderOpen, rgb(0x38bdf8)))
                    .child(
                        v_flex()
                            .flex_1()
                            .min_w(px(0.))
                            .overflow_hidden()
                            .gap_1()
                            .child(ui::row_title(repo.name.clone()))
                            .child(ui::row_meta(repo.path.clone())),
                    )
                    .child(if task_default {
                        status_pill("task default", color::primary())
                    } else {
                        div()
                    })
                    .child(status_pill(worktree_count_label, rgb(0x38bdf8))),
            )
            .child(
                h_flex()
                    .justify_between()
                    .gap_2()
                    .flex_wrap()
                    .child(label("Worktrees"))
                    .child(small_text(format!("Updated {}", repo.updated_at))),
            )
            .child(worktree_list)
            .child(
                h_flex()
                    .gap_2()
                    .flex_wrap()
                    .child(
                        Button::new(format!("select-repo-{}", repo.id))
                            .small()
                            .selected(task_default)
                            .label(if task_default {
                                "Default for new tasks"
                            } else {
                                "Use for new tasks"
                            })
                            .on_click({
                                let app = cx.entity().downgrade();
                                move |_, _, cx| {
                                    let _ = app.update(cx, |state, cx| {
                                        state.task_repository_id = Some(repo_id.clone());
                                        state.banner = Some(Banner {
                                            kind: BannerKind::Info,
                                            text: "Repository selected for new tasks.".to_owned(),
                                        });
                                        cx.notify();
                                    });
                                }
                            }),
                    )
                    .child(
                        Button::new(format!("delete-repo-{}", repo.id))
                            .small()
                            .danger()
                            .label("Delete")
                            .on_click({
                                let app = cx.entity().downgrade();
                                move |_, _, cx| {
                                    let _ = app.update(cx, |state, cx| {
                                        let delete_id = delete_id.clone();
                                        state.run_api(
                                            "delete-repository",
                                            cx,
                                            move |client| client.delete_repository(&delete_id),
                                            |state, result, cx| {
                                                state.set_result_banner(
                                                    &result,
                                                    "Repository deleted.",
                                                );
                                                state.refresh_repositories(cx);
                                            },
                                        );
                                    });
                                }
                            }),
                    ),
            )
            .into_any_element()
    }

    fn render_repositories_page(&self, cx: &mut Context<Self>) -> Div {
        let app = cx.entity().downgrade();
        let create = card(
            "Register Repository",
            v_flex()
                .gap_3()
                .child(label("Path"))
                .child(Input::new(&self.repository_path))
                .child(label("Display name"))
                .child(Input::new(&self.repository_name))
                .child(
                    Button::new("create-repository")
                        .primary()
                        .small()
                        .icon(IconName::Plus)
                        .label("Register")
                        .on_click(move |_, _, cx| {
                            let _ = app.update(cx, |state, cx| state.submit_repository(cx));
                        }),
                ),
        );

        let repository_count = self.repositories.len();
        let total_worktrees: usize = self.worktrees.values().map(Vec::len).sum();
        let summary = h_flex()
            .justify_between()
            .gap_3()
            .flex_wrap()
            .child(
                h_flex()
                    .gap_2()
                    .flex_wrap()
                    .child(status_pill(
                        format!(
                            "{} {}",
                            repository_count,
                            if repository_count == 1 {
                                "repository"
                            } else {
                                "repositories"
                            }
                        ),
                        color::primary(),
                    ))
                    .child(status_pill(
                        format!(
                            "{} {}",
                            total_worktrees,
                            if total_worktrees == 1 {
                                "worktree"
                            } else {
                                "worktrees"
                            }
                        ),
                        rgb(0x38bdf8),
                    )),
            )
            .child(if self.loading.contains("repositories") {
                status_pill("Loading...", rgb(0x94a3b8))
            } else {
                div()
            });
        let repository_body = if self.repositories.is_empty() {
            ui::empty_state(
                IconName::FolderOpen,
                "No repositories",
                "Register a local git repository before assigning coding or review tasks.",
            )
            .into_any_element()
        } else {
            list(
                self.repository_list_state.clone(),
                cx.processor(move |this, index: usize, _window, cx| {
                    this.repositories
                        .get(index)
                        .map(|repo| {
                            div()
                                .w_full()
                                .pb_3()
                                .child(this.render_repository_row(repo, cx))
                                .into_any_element()
                        })
                        .unwrap_or_else(|| div().into_any_element())
                }),
            )
            .size_full()
            .into_any_element()
        };
        let repositories = card(
            "Repositories",
            v_flex()
                .flex_1()
                .min_h(px(0.))
                .gap_3()
                .child(summary)
                .child(
                    div()
                        .flex_1()
                        .min_h(px(0.))
                        .overflow_hidden()
                        .child(repository_body),
                ),
        )
        .w_full()
        .h_full()
        .min_h(px(0.));

        let mut rail_content = v_flex().gap_3().child(create);
        if let Some(repo) = self.selected_repository() {
            let worktree_count = self.worktrees.get(&repo.id).map(Vec::len).unwrap_or(0);
            let task_default = self.task_repository_id.as_deref() == Some(repo.id.as_str());
            rail_content = rail_content.child(card(
                "Selected Repository",
                v_flex()
                    .gap_2()
                    .child(ui::row_title(repo.name.clone()))
                    .child(if task_default {
                        status_pill("Default for new tasks", color::primary())
                    } else {
                        status_pill("Available", rgb(0x38bdf8))
                    })
                    .child(ui::kv_row("Path", repo.path.clone()))
                    .child(ui::kv_row("Worktrees", worktree_count.to_string()))
                    .child(ui::kv_row("Created", repo.created_at.clone()))
                    .child(ui::kv_row("Updated", repo.updated_at.clone())),
            ));
        }
        let rail = ui::side_rail()
            .h_full()
            .min_h(px(0.))
            .overflow_hidden()
            .child(
                div()
                    .id("repositories-rail-scroll-frame")
                    .size_full()
                    .overflow_y_scrollbar()
                    .pr_1()
                    .child(rail_content),
            );

        h_flex()
            .size_full()
            .min_h(px(0.))
            .items_stretch()
            .gap_4()
            .overflow_hidden()
            .child(
                ui::content_region()
                    .h_full()
                    .min_h(px(0.))
                    .child(repositories),
            )
            .child(rail)
    }

    fn render_conversation_page(&self, mode: &'static str, cx: &mut Context<Self>) -> Div {
        let session = if mode == "chat" {
            self.chat_session.as_ref()
        } else {
            self.agent_session.as_ref()
        };
        let input = if mode == "chat" {
            &self.chat_prompt
        } else {
            &self.agent_prompt
        };
        let accent = if mode == "chat" {
            rgb(0x22d3ee)
        } else {
            rgb(0xf97316)
        };
        let empty_title = if mode == "chat" {
            "Ask Nina anything"
        } else {
            "Run an agent task"
        };
        let empty_detail = if mode == "chat" {
            "Start a local-context conversation with your notes, tasks, jobs, and repositories."
        } else {
            "Describe the operation you want Nina to perform and review the response here."
        };
        let title = session
            .and_then(|session| session.title.clone())
            .unwrap_or_else(|| {
                if mode == "chat" {
                    "Chat session".to_owned()
                } else {
                    "Agent session".to_owned()
                }
            });
        let message_count = self.message_cache(mode).len();
        let list_state = self.conversation_list_state(mode);
        let header = h_flex()
            .justify_between()
            .items_start()
            .gap_3()
            .child(
                v_flex()
                    .min_w(px(0.))
                    .gap_1()
                    .child(ui::row_title(title))
                    .child(ui::row_meta(if let Some(session) = session {
                        format!(
                            "{} messages - updated {}",
                            message_count, session.updated_at
                        )
                    } else {
                        "No active session".to_owned()
                    })),
            )
            .child(status_pill(mode, accent));
        let history_panel = if session.is_some() {
            if message_count == 0 {
                ui::chat_history().child(
                    v_flex()
                        .id(format!("{mode}-empty-history-scroll"))
                        .size_full()
                        .min_h(px(0.))
                        .gap_3()
                        .p_4()
                        .overflow_y_scrollbar()
                        .child(header)
                        .child(ui::empty_state(
                            if mode == "chat" {
                                IconName::BookOpen
                            } else {
                                IconName::Bot
                            },
                            empty_title,
                            empty_detail,
                        )),
                )
            } else {
                ui::chat_history()
                    .child(div().w_full().p_4().pb_3().flex_shrink_0().child(header))
                    .child(
                        div().flex_1().min_h(px(0.)).child(
                            list(
                                list_state.clone(),
                                cx.processor(move |this, index: usize, _window, _cx| {
                                    this.message_cache(mode)
                                        .get(index)
                                        .map(|message| {
                                            div()
                                                .w_full()
                                                .px_4()
                                                .pb_3()
                                                .child(render_cached_chat_message(message, accent))
                                                .into_any_element()
                                        })
                                        .unwrap_or_else(|| div().into_any_element())
                                }),
                            )
                            .size_full(),
                        ),
                    )
            }
        } else {
            ui::chat_history().child(
                v_flex()
                    .id(format!("{mode}-inactive-history-scroll"))
                    .size_full()
                    .min_h(px(0.))
                    .gap_3()
                    .p_4()
                    .overflow_y_scrollbar()
                    .child(header)
                    .child(ui::empty_state(
                        if mode == "chat" {
                            IconName::BookOpen
                        } else {
                            IconName::Bot
                        },
                        empty_title,
                        empty_detail,
                    )),
            )
        };
        let app_send = cx.entity().downgrade();
        let app_cancel = cx.entity().downgrade();
        let app_clear = cx.entity().downgrade();
        let send_label = format!("{mode}-send");
        let clear_label = format!("{mode}-clear");
        let sending = self.loading.contains(&send_label);
        let clearing = self.loading.contains(&clear_label);
        ui::chat_canvas().child(history_panel).child(
            ui::chat_composer().child(Input::new(input)).child(
                h_flex()
                    .justify_between()
                    .gap_2()
                    .child(if sending {
                        status_pill("Sending...", color::primary())
                    } else if mode == "chat" {
                        ui::row_meta("Local context chat")
                    } else {
                        ui::row_meta("Nina agent session")
                    })
                    .child(
                        h_flex()
                            .gap_2()
                            .child(
                                Button::new(format!("{mode}-clear"))
                                    .small()
                                    .label(if clearing { "Clearing..." } else { "Clear" })
                                    .on_click(move |_, window, cx| {
                                        let _ = app_clear.update(cx, |state, cx| {
                                            state.clear_conversation(mode, window, cx)
                                        });
                                    }),
                            )
                            .child(
                                Button::new(format!("{mode}-cancel"))
                                    .small()
                                    .label("Cancel")
                                    .on_click(move |_, _, cx| {
                                        let _ = app_cancel
                                            .update(cx, |state, cx| state.cancel_session(mode, cx));
                                    }),
                            )
                            .child(
                                Button::new(format!("{mode}-send"))
                                    .primary()
                                    .small()
                                    .label(if sending { "Sending..." } else { "Send" })
                                    .on_click(move |_, window, cx| {
                                        let _ = app_send.update(cx, |state, cx| {
                                            state.send_prompt(mode, window, cx)
                                        });
                                    }),
                            ),
                    ),
            ),
        )
    }

    fn render_research_page(&self, cx: &mut Context<Self>) -> Div {
        let running = self.loading.contains("research");
        let mut mode_buttons = h_flex().gap_2().flex_wrap();
        for (label_text, mode) in [
            ("Default", None),
            ("Live", Some("live")),
            ("Cached", Some("cached")),
            ("Disabled", Some("disabled")),
        ] {
            let next_mode = mode.map(str::to_owned);
            let selected = self.research_search_mode == next_mode;
            let app = cx.entity().downgrade();
            mode_buttons = mode_buttons.child(
                Button::new(format!("research-mode-{label_text}"))
                    .small()
                    .selected(selected)
                    .disabled(running)
                    .label(label_text)
                    .on_click(move |_, _, cx| {
                        let _ = app.update(cx, |state, cx| {
                            state.research_search_mode = next_mode.clone();
                            cx.notify();
                        });
                    }),
            );
        }
        let app = cx.entity().downgrade();
        let app_open = cx.entity().downgrade();
        let report = self
            .research_report
            .as_ref()
            .map(|report| {
                let mut sources = v_flex().gap_2();
                for source in &report.sources {
                    sources = sources.child(
                        ui::compact_row(false, rgb(0xeab308))
                            .cursor_default()
                            .child(ui::icon_badge(IconName::Globe, rgb(0xeab308)))
                            .child(
                                v_flex()
                                    .flex_1()
                                    .overflow_hidden()
                                    .gap_1()
                                    .child(ui::row_title(source.title.clone()))
                                    .child(ui::row_meta(source.url.clone())),
                            ),
                    );
                }
                if report.sources.is_empty() {
                    sources = sources.child(ui::row_meta("No sources returned."));
                }
                ui::page_stack()
                    .child(card(
                        format!("Report - {}", report.note_path),
                        v_flex()
                            .gap_3()
                            .child(
                                h_flex()
                                    .gap_2()
                                    .flex_wrap()
                                    .child(status_pill(
                                        report.status.clone().unwrap_or_else(|| "done".to_owned()),
                                        rgb(0x22c55e),
                                    ))
                                    .child(status_pill(
                                        report
                                            .search_mode
                                            .clone()
                                            .unwrap_or_else(|| "default".to_owned()),
                                        rgb(0x38bdf8),
                                    ))
                                    .child(status_pill(
                                        report
                                            .provider
                                            .clone()
                                            .unwrap_or_else(|| "provider".to_owned()),
                                        rgb(0xeab308),
                                    )),
                            )
                            .child(div().child(report.summary.clone())),
                    ))
                    .child(card("Sources", sources))
            })
            .unwrap_or_else(|| {
                if running {
                    ui::empty_state(
                        IconName::Globe,
                        "Research running",
                        "Waiting for the daemon response.",
                    )
                } else {
                    ui::empty_state(
                        IconName::Globe,
                        "No research report yet",
                        "Enter a topic and run research.",
                    )
                }
            });
        ui::page_columns()
            .child(
                ui::side_rail().child(card(
                    "Run Research",
                    v_flex()
                        .gap_3()
                        .child(Input::new(&self.research_topic).disabled(running))
                        .child(if running {
                            status_pill("Running...", color::primary())
                        } else {
                            status_pill(
                                self.research_search_mode
                                    .clone()
                                    .unwrap_or_else(|| "default search".to_owned()),
                                rgb(0x38bdf8),
                            )
                        })
                        .child(label("Search mode"))
                        .child(mode_buttons)
                        .child(
                            h_flex()
                                .gap_2()
                                .child(
                                    Button::new("run-research")
                                        .primary()
                                        .small()
                                        .loading(running)
                                        .disabled(running)
                                        .label(if running { "Running..." } else { "Run" })
                                        .on_click(move |_, _, cx| {
                                            let _ = app
                                                .update(cx, |state, cx| state.run_research(cx));
                                        }),
                                )
                                .child(
                                    Button::new("open-research")
                                        .small()
                                        .disabled(running || self.research_report.is_none())
                                        .label("Open Note")
                                        .on_click(move |_, _, cx| {
                                            let _ = app_open.update(cx, |state, cx| {
                                                let Some(report) = state.research_report.clone()
                                                else {
                                                    state.banner =
                                                        Some(error_text("No research note yet."));
                                                    cx.notify();
                                                    return;
                                                };
                                                state.run_api(
                                                    "open-research",
                                                    cx,
                                                    move |client| client.open_note(report.note_path),
                                                    |state, result, _| {
                                                        state.set_result_banner(
                                                            &result,
                                                            "Requested Obsidian to open the research note.",
                                                        );
                                                    },
                                                );
                                            });
                                        }),
                                ),
                        ),
                )),
            )
            .child(ui::content_region().child(report))
    }

    fn render_meeting_row(&self, meeting: &Meeting, cx: &mut Context<Self>) -> AnyElement {
        let select_id = meeting.id.clone();
        let selected = self.selected_meeting_id.as_deref() == Some(meeting.id.as_str());
        let status_color = meeting_status_color(&meeting.status);
        let artifact_color = rgb(0x64748b);
        let artifact_pills = h_flex()
            .gap_2()
            .flex_wrap()
            .child(status_pill(meeting.source.clone(), status_color))
            .child(status_pill(meeting_duration_text(meeting), artifact_color))
            .child(if meeting.note_path.is_some() {
                status_pill("note", rgb(0x22c55e))
            } else {
                div()
            })
            .child(if meeting.transcript_note_path.is_some() {
                status_pill("transcript", rgb(0x38bdf8))
            } else {
                div()
            })
            .child(if meeting.summary_note_path.is_some() {
                status_pill("summary", color::primary())
            } else {
                div()
            });
        ui::surface_block()
            .child(
                ui::compact_row(selected, status_color)
                    .min_h(px(60.))
                    .id(format!("meeting-row-{}", meeting.id))
                    .on_click({
                        let app = cx.entity().downgrade();
                        move |_, _, cx| {
                            let _ = app.update(cx, |state, cx| {
                                state.selected_meeting_id = Some(select_id.clone());
                                cx.notify();
                            });
                        }
                    })
                    .child(ui::icon_badge(IconName::Calendar, status_color))
                    .child(
                        v_flex()
                            .flex_1()
                            .min_w(px(0.))
                            .overflow_hidden()
                            .gap_1()
                            .child(ui::row_title(meeting.title.clone()))
                            .child(ui::row_meta(format!(
                                "Started {} - ended {}",
                                meeting.started_at,
                                option_text(&meeting.ended_at)
                            ))),
                    )
                    .child(status_pill(meeting.status.clone(), status_color)),
            )
            .child(artifact_pills)
            .child(self.render_meeting_actions("row", meeting, cx))
            .into_any_element()
    }

    fn render_meetings_page(&self, cx: &mut Context<Self>) -> Div {
        let recording = self.loading.contains("record-meeting");
        let mut source_buttons = h_flex().gap_2().flex_wrap();
        for source in ["mic", "system", "mixed"] {
            let next = source.to_owned();
            let app = cx.entity().downgrade();
            source_buttons = source_buttons.child(
                Button::new(format!("meeting-source-{source}"))
                    .small()
                    .selected(self.meeting_source == source)
                    .disabled(recording)
                    .label(source)
                    .on_click(move |_, _, cx| {
                        let _ = app.update(cx, |state, cx| {
                            state.meeting_source = next.clone();
                            cx.notify();
                        });
                    }),
            );
        }
        let app = cx.entity().downgrade();
        let controls = card(
            "Recording",
            v_flex()
                .gap_3()
                .child(label("Title"))
                .child(Input::new(&self.meeting_title).disabled(recording))
                .child(label("Source"))
                .child(source_buttons)
                .child(
                    Button::new("start-meeting")
                        .primary()
                        .small()
                        .loading(recording)
                        .disabled(recording)
                        .label(if recording {
                            "Starting..."
                        } else {
                            "Start Recording"
                        })
                        .on_click(move |_, _, cx| {
                            let _ = app.update(cx, |state, cx| state.start_recording(cx));
                        }),
                ),
        );

        let total_meetings = self.meetings.len();
        let recording_count = self
            .meetings
            .iter()
            .filter(|meeting| meeting.status == "recording")
            .count();
        let selected_label = self
            .selected_meeting()
            .map(|meeting| compact_text(&meeting.title, 36))
            .unwrap_or_else(|| "No meeting selected".to_owned());
        let summary = h_flex()
            .justify_between()
            .gap_3()
            .flex_wrap()
            .child(
                h_flex()
                    .gap_2()
                    .flex_wrap()
                    .child(status_pill(
                        format!(
                            "{} {}",
                            total_meetings,
                            if total_meetings == 1 {
                                "meeting"
                            } else {
                                "meetings"
                            }
                        ),
                        color::primary(),
                    ))
                    .child(if recording_count > 0 {
                        status_pill(format!("{recording_count} recording"), rgb(0xef4444))
                    } else {
                        status_pill("idle", rgb(0x64748b))
                    })
                    .child(status_pill(selected_label, rgb(0x38bdf8))),
            )
            .child(if self.loading.contains("meetings") {
                status_pill("Loading...", rgb(0x94a3b8))
            } else {
                div()
            });

        let list = if self.meetings.is_empty() {
            ui::empty_state(
                IconName::Calendar,
                "No meetings recorded",
                "Start a recording to capture audio, transcripts, summaries, and meeting notes.",
            )
            .into_any_element()
        } else {
            list(
                self.meeting_list_state.clone(),
                cx.processor(move |this, index: usize, _window, cx| {
                    this.meetings
                        .get(index)
                        .map(|meeting| {
                            div()
                                .w_full()
                                .pb_2()
                                .child(this.render_meeting_row(meeting, cx))
                                .into_any_element()
                        })
                        .unwrap_or_else(|| div().into_any_element())
                }),
            )
            .size_full()
            .into_any_element()
        };

        let main = v_flex()
            .flex_1()
            .min_w(px(520.))
            .h_full()
            .min_h(px(0.))
            .child(
                card(
                    "Meetings",
                    v_flex()
                        .flex_1()
                        .min_h(px(0.))
                        .gap_3()
                        .child(summary)
                        .child(
                            div()
                                .flex_1()
                                .min_h(px(0.))
                                .overflow_hidden()
                                .pr_1()
                                .child(list),
                        ),
                )
                .w_full()
                .h_full()
                .min_h(px(0.)),
            );

        let mut rail_content = v_flex().gap_3().child(controls);
        if let Some(meeting) = self.selected_meeting() {
            rail_content = rail_content
                .child(card(
                    "Selected Actions",
                    self.render_meeting_actions("selected", meeting, cx),
                ))
                .child(card(
                    "Selected Meeting",
                    v_flex()
                        .gap_2()
                        .child(ui::row_title(meeting.title.clone()))
                        .child(status_pill(
                            meeting.status.clone(),
                            meeting_status_color(&meeting.status),
                        ))
                        .child(ui::kv_row("Source", meeting.source.clone()))
                        .child(ui::kv_row("Started", meeting.started_at.clone()))
                        .child(ui::kv_row("Ended", option_text(&meeting.ended_at)))
                        .child(ui::kv_row("Duration", meeting_duration_text(meeting)))
                        .child(ui::kv_row("Format", meeting.audio_format.clone()))
                        .child(ui::kv_row("Sample rate", meeting.sample_rate.to_string()))
                        .child(ui::kv_row("Channels", meeting.channels.to_string()))
                        .child(ui::kv_row("Audio", meeting.audio_path.clone()))
                        .child(ui::kv_row("Note", option_text(&meeting.note_path)))
                        .child(ui::kv_row(
                            "Transcript",
                            option_text(&meeting.transcript_note_path),
                        ))
                        .child(ui::kv_row(
                            "Summary",
                            option_text(&meeting.summary_note_path),
                        )),
                ));
        }

        let rail = v_flex()
            .w(px(360.))
            .min_w(px(320.))
            .h_full()
            .min_h(px(0.))
            .flex_shrink_0()
            .overflow_hidden()
            .child(
                div()
                    .id("meetings-rail-scroll-frame")
                    .size_full()
                    .overflow_y_scrollbar()
                    .pr_1()
                    .child(rail_content),
            );

        h_flex()
            .size_full()
            .min_h(px(0.))
            .items_stretch()
            .gap_4()
            .overflow_hidden()
            .child(main)
            .child(rail)
    }

    fn render_meeting_actions(
        &self,
        id_scope: &'static str,
        meeting: &Meeting,
        cx: &mut Context<Self>,
    ) -> Div {
        let stop_id = meeting.id.clone();
        let pipeline_id = meeting.id.clone();
        let note_path = meeting.note_path.clone();
        let summary_note_path = meeting.summary_note_path.clone();
        let transcript_note_path = meeting.transcript_note_path.clone();
        let play_id = meeting.id.clone();
        let delete_id = meeting.id.clone();
        h_flex()
            .gap_2()
            .flex_wrap()
            .child(if meeting.status == "recording" {
                Button::new(format!("{id_scope}-stop-meeting-{}", meeting.id))
                    .small()
                    .danger()
                    .label("Stop")
                    .on_click({
                        let app = cx.entity().downgrade();
                        move |_, _, cx| {
                            let _ = app.update(cx, |state, cx| {
                                let stop_id = stop_id.clone();
                                state.run_api(
                                    "stop-meeting",
                                    cx,
                                    move |client| client.stop_meeting(&stop_id),
                                    |state, result, cx| {
                                        state.set_result_banner(&result, "Recording stopped.");
                                        state.refresh_meetings(cx);
                                    },
                                );
                            });
                        }
                    })
                    .into_any_element()
            } else {
                div().into_any_element()
            })
            .child(
                Button::new(format!("{id_scope}-pipeline-meeting-{}", meeting.id))
                    .small()
                    .label("Transcribe + summarize")
                    .on_click({
                        let app = cx.entity().downgrade();
                        move |_, _, cx| {
                            let _ = app.update(cx, |state, cx| {
                                let pipeline_id = pipeline_id.clone();
                                state.run_api(
                                    "meeting-pipeline",
                                    cx,
                                    move |client| client.run_meeting_pipeline(&pipeline_id),
                                    |state, result, cx| {
                                        state.set_result_banner(
                                            &result,
                                            "Meeting pipeline complete.",
                                        );
                                        state.refresh_meetings(cx);
                                    },
                                );
                            });
                        }
                    }),
            )
            .child(self.render_open_note_button(
                format!("{id_scope}-open-meeting-{}", meeting.id),
                "Open Note",
                note_path,
                "Meeting has no note yet.",
                "Opened the meeting note.",
                cx,
            ))
            .child(self.render_open_note_button(
                format!("{id_scope}-open-transcript-{}", meeting.id),
                "Transcript",
                transcript_note_path,
                "Meeting has no transcript note yet.",
                "Opened the meeting transcript.",
                cx,
            ))
            .child(self.render_open_note_button(
                format!("{id_scope}-open-summary-{}", meeting.id),
                "Summary",
                summary_note_path,
                "Meeting has no summary note yet.",
                "Opened the meeting summary.",
                cx,
            ))
            .child(
                Button::new(format!("{id_scope}-play-meeting-{}", meeting.id))
                    .small()
                    .label("Play")
                    .on_click({
                        let app = cx.entity().downgrade();
                        move |_, _, cx| {
                            let _ = app.update(cx, |state, cx| {
                                state.play_meeting(&play_id);
                                cx.notify();
                            });
                        }
                    }),
            )
            .child(
                Button::new(format!("{id_scope}-delete-meeting-{}", meeting.id))
                    .small()
                    .danger()
                    .label("Delete")
                    .on_click({
                        let app = cx.entity().downgrade();
                        move |_, _, cx| {
                            let _ = app.update(cx, |state, cx| {
                                let delete_id = delete_id.clone();
                                state.run_api(
                                    "delete-meeting",
                                    cx,
                                    move |client| client.delete_meeting(&delete_id),
                                    |state, result, cx| {
                                        state.set_result_banner(&result, "Meeting deleted.");
                                        state.refresh_meetings(cx);
                                    },
                                );
                            });
                        }
                    }),
            )
    }

    fn render_open_note_button(
        &self,
        id: String,
        label: &'static str,
        path: Option<String>,
        missing_message: &'static str,
        success_message: &'static str,
        cx: &mut Context<Self>,
    ) -> Button {
        let disabled = path.is_none();
        Button::new(id)
            .small()
            .label(label)
            .disabled(disabled)
            .on_click({
                let app = cx.entity().downgrade();
                move |_, _, cx| {
                    let _ = app.update(cx, |state, cx| {
                        let Some(path) = path.clone() else {
                            state.banner = Some(error_text(missing_message));
                            cx.notify();
                            return;
                        };
                        state.run_api(
                            "open-note",
                            cx,
                            move |client| client.open_note(path),
                            move |state, result, _| {
                                state.set_result_banner(&result, success_message);
                            },
                        );
                    });
                }
            })
    }

    fn play_meeting(&mut self, meeting_id: &str) {
        let Some(meeting) = self
            .meetings
            .iter()
            .find(|meeting| meeting.id == meeting_id)
        else {
            self.banner = Some(error_text("Meeting not found."));
            return;
        };
        let template = self
            .config
            .as_ref()
            .map(|config| config.meetings.play_command.clone())
            .unwrap_or_else(|| "xdg-open {path}".to_owned());
        let parts = split_command(&template, &meeting.audio_path);
        let Some((binary, args)) = parts else {
            self.banner = Some(error_text("meetings.play_command is empty."));
            return;
        };
        match Command::new(binary).args(args).spawn() {
            Ok(_) => {
                self.banner = Some(Banner {
                    kind: BannerKind::Info,
                    text: format!("Playing {}.", meeting.audio_path),
                });
            }
            Err(err) => {
                self.banner = Some(error_text(format!("Could not launch player: {err}")));
            }
        }
    }

    fn render_job_row(&self, job: &Job, cx: &mut Context<Self>) -> AnyElement {
        let select_name = job.name.clone();
        let button_name = job.name.clone();
        let run_name = job.name.clone();
        let selected = self.selected_job_name.as_deref() == Some(job.name.as_str());
        let status_color = if job.enabled {
            rgb(0x22c55e)
        } else {
            rgb(0x64748b)
        };
        ui::surface_block()
            .child(
                ui::compact_row(selected, status_color)
                    .id(format!("job-row-{}", job.name))
                    .on_click({
                        let app = cx.entity().downgrade();
                        move |_, _, cx| {
                            let _ = app.update(cx, |state, cx| {
                                state.refresh_job_runs(select_name.clone(), cx)
                            });
                        }
                    })
                    .child(ui::icon_badge(IconName::Cpu, status_color))
                    .child(
                        v_flex()
                            .flex_1()
                            .overflow_hidden()
                            .gap_1()
                            .child(ui::row_title(format!(
                                "{} ({})",
                                job.name, job.workflow_name
                            )))
                            .child(ui::row_meta(format!(
                                "last: {} - next: {}",
                                option_text(&job.last_run_at),
                                option_text(&job.next_run_at)
                            ))),
                    )
                    .child(status_pill(
                        if job.enabled { "enabled" } else { "disabled" },
                        status_color,
                    )),
            )
            .child(
                h_flex()
                    .gap_2()
                    .child(
                        Button::new(format!("select-job-{}", job.name))
                            .small()
                            .label("Runs")
                            .on_click({
                                let app = cx.entity().downgrade();
                                move |_, _, cx| {
                                    let _ = app.update(cx, |state, cx| {
                                        state.refresh_job_runs(button_name.clone(), cx)
                                    });
                                }
                            }),
                    )
                    .child(
                        Button::new(format!("run-job-{}", job.name))
                            .small()
                            .label("Run now")
                            .on_click({
                                let app = cx.entity().downgrade();
                                move |_, _, cx| {
                                    let _ = app.update(cx, |state, cx| {
                                        let run_name = run_name.clone();
                                        state.run_api(
                                            "run-job",
                                            cx,
                                            move |client| client.run_job(&run_name),
                                            |state, result, cx| {
                                                state
                                                    .set_result_banner(&result, "Job run started.");
                                                state.refresh_jobs(cx);
                                            },
                                        );
                                    });
                                }
                            }),
                    ),
            )
            .into_any_element()
    }

    fn render_job_run_row(&self, run: &JobRun) -> AnyElement {
        let color = if run.status == "completed" {
            rgb(0x22c55e)
        } else if run.status == "failed" {
            rgb(0xef4444)
        } else {
            rgb(0x38bdf8)
        };
        ui::compact_row(false, color)
            .cursor_default()
            .child(ui::icon_badge(IconName::Redo, color))
            .child(
                v_flex()
                    .flex_1()
                    .overflow_hidden()
                    .gap_1()
                    .child(ui::row_title(format!(
                        "{} - {}",
                        short_id(&run.id),
                        run.status
                    )))
                    .child(ui::row_meta(format!(
                        "Started: {} - Completed: {}",
                        option_text(&run.started_at),
                        option_text(&run.completed_at)
                    )))
                    .child(ui::row_meta(run.error.clone().unwrap_or_default())),
            )
            .into_any_element()
    }

    fn render_workflow_row(&self, workflow: &WorkflowInfo) -> AnyElement {
        ui::compact_row(false, rgb(0x38bdf8))
            .cursor_default()
            .child(ui::icon_badge(IconName::Network, rgb(0x38bdf8)))
            .child(
                v_flex()
                    .flex_1()
                    .overflow_hidden()
                    .gap_1()
                    .child(ui::row_title(workflow.name.clone()))
                    .child(ui::row_meta(workflow.description.clone())),
            )
            .into_any_element()
    }

    fn render_jobs_page(&self, cx: &mut Context<Self>) -> Div {
        let jobs_body = if self.jobs.is_empty() {
            ui::empty_state(
                IconName::Cpu,
                "No scheduled jobs",
                "Configured scheduler jobs will appear here with run history and manual triggers.",
            )
            .into_any_element()
        } else {
            list(
                self.job_list_state.clone(),
                cx.processor(move |this, index: usize, _window, cx| {
                    this.jobs
                        .get(index)
                        .map(|job| {
                            div()
                                .w_full()
                                .pb_2()
                                .child(this.render_job_row(job, cx))
                                .into_any_element()
                        })
                        .unwrap_or_else(|| div().into_any_element())
                }),
            )
            .size_full()
            .into_any_element()
        };
        let runs_body = if self.job_runs.is_empty() {
            ui::empty_state(
                IconName::Redo,
                "No runs selected",
                "Choose a job to inspect recent runs, status, and errors.",
            )
            .into_any_element()
        } else {
            list(
                self.job_run_list_state.clone(),
                cx.processor(move |this, index: usize, _window, _cx| {
                    this.job_runs
                        .get(index)
                        .map(|run| {
                            div()
                                .w_full()
                                .pb_2()
                                .child(this.render_job_run_row(run))
                                .into_any_element()
                        })
                        .unwrap_or_else(|| div().into_any_element())
                }),
            )
            .size_full()
            .into_any_element()
        };
        let workflows_body = if self.workflows.is_empty() {
            ui::empty_state(
                IconName::Network,
                "No workflows",
                "Workflow metadata has not loaded yet.",
            )
            .into_any_element()
        } else {
            list(
                self.workflow_list_state.clone(),
                cx.processor(move |this, index: usize, _window, _cx| {
                    this.workflows
                        .get(index)
                        .map(|workflow| {
                            div()
                                .w_full()
                                .pb_2()
                                .child(this.render_workflow_row(workflow))
                                .into_any_element()
                        })
                        .unwrap_or_else(|| div().into_any_element())
                }),
            )
            .size_full()
            .into_any_element()
        };

        let jobs = card(
            "Jobs",
            div()
                .flex_1()
                .min_h(px(0.))
                .overflow_hidden()
                .child(jobs_body),
        )
        .w_full()
        .h_full()
        .min_h(px(0.));
        let runs = card(
            self.selected_job()
                .map(|job| format!("Runs - {}", job.name))
                .unwrap_or_else(|| "Runs".to_owned()),
            div()
                .flex_1()
                .min_h(px(0.))
                .overflow_hidden()
                .child(runs_body),
        )
        .w_full()
        .h_full()
        .min_h(px(0.));
        let workflows = card(
            "Workflows",
            div()
                .flex_1()
                .min_h(px(0.))
                .overflow_hidden()
                .child(workflows_body),
        )
        .w_full()
        .h_full()
        .min_h(px(0.));

        h_flex()
            .size_full()
            .min_h(px(0.))
            .items_stretch()
            .gap_4()
            .overflow_hidden()
            .child(ui::content_region().h_full().min_h(px(0.)).child(jobs))
            .child(
                v_flex()
                    .w(px(360.))
                    .min_w(px(320.))
                    .h_full()
                    .min_h(px(0.))
                    .flex_shrink_0()
                    .child(runs),
            )
            .child(
                v_flex()
                    .w(px(360.))
                    .min_w(px(300.))
                    .h_full()
                    .min_h(px(0.))
                    .flex_shrink_0()
                    .child(workflows),
            )
    }

    fn render_integration_row(
        &self,
        integration: &IntegrationRecord,
        cx: &mut Context<Self>,
    ) -> AnyElement {
        let selected_name = self
            .selected_integration_name
            .as_deref()
            .or_else(|| self.integrations.first().map(|item| item.name.as_str()));
        let name = integration.name.clone();
        let color = integration_status_color(&integration.status);
        let selected = selected_name == Some(integration.name.as_str());
        let app = cx.entity().downgrade();
        ui::compact_row(selected, color)
            .id(format!("integration-select-{}", integration.name))
            .min_h(px(76.))
            .on_click(move |_, window, cx| {
                let _ = app.update(cx, |state, cx| {
                    state.select_integration(name.clone(), window, cx);
                });
            })
            .child(ui::icon_badge(IconName::Network, color))
            .child(
                v_flex()
                    .flex_1()
                    .min_w(px(0.))
                    .overflow_hidden()
                    .gap_1()
                    .child(ui::row_title(integration.display_name.clone()))
                    .child(ui::row_meta(integration.description.clone()))
                    .child(ui::row_meta(integration_last_text(integration))),
            )
            .child(status_pill(&integration.status, color))
            .into_any_element()
    }

    fn render_integrations_page(&self, cx: &mut Context<Self>) -> Div {
        let list = if self.integrations.is_empty() {
            ui::empty_state(
                IconName::Network,
                "No integrations",
                "External integration health will appear here when the daemon reports it.",
            )
            .into_any_element()
        } else {
            list(
                self.integration_list_state.clone(),
                cx.processor(move |this, index: usize, _window, cx| {
                    this.integrations
                        .get(index)
                        .map(|integration| {
                            div()
                                .w_full()
                                .pb_2()
                                .child(this.render_integration_row(integration, cx))
                                .into_any_element()
                        })
                        .unwrap_or_else(|| div().into_any_element())
                }),
            )
            .size_full()
            .into_any_element()
        };

        let details = if let Some(integration) = self
            .selected_integration()
            .or_else(|| self.integrations.first())
        {
            let mut fields = v_flex().gap_3();
            for field in &integration.credential_fields {
                let configured = integration
                    .configured_fields
                    .get(&field.name)
                    .copied()
                    .unwrap_or(false);
                let field_status = if configured {
                    status_pill("set", rgb(0x22c55e))
                } else if field.required {
                    status_pill("required", rgb(0xf97316))
                } else {
                    status_pill("optional", rgb(0x94a3b8))
                };
                let mut field_row = v_flex().gap_1().child(
                    h_flex()
                        .justify_between()
                        .gap_2()
                        .child(label(field.label.clone()))
                        .child(field_status),
                );
                if let Some(input) = self.credential_input(&field.name) {
                    let mut input_element = Input::new(&input).cleanable(true);
                    if field.secret {
                        input_element = input_element.mask_toggle();
                    }
                    field_row = field_row.child(input_element);
                } else {
                    field_row =
                        field_row.child(small_text(format!("Unsupported field: {}", field.name)));
                }
                if let Some(placeholder) = &field.placeholder {
                    field_row = field_row.child(ui::row_meta(placeholder.clone()));
                }
                fields = fields.child(field_row);
            }
            if integration.credential_fields.is_empty() {
                fields = fields.child(ui::empty_state(
                    IconName::Network,
                    "No credential fields",
                    "This integration does not expose desktop-editable credential fields.",
                ));
            }

            let save_label = format!("save-integration-{}", integration.name);
            let clear_label = format!("clear-integration-{}", integration.name);
            let test_label = format!("test-integration-{}", integration.name);
            let saving = self.loading.contains(&save_label);
            let clearing = self.loading.contains(&clear_label);
            let testing = self.loading.contains(&test_label);
            let save_app = cx.entity().downgrade();
            let clear_app = cx.entity().downgrade();
            let test_app = cx.entity().downgrade();
            let test_name = integration.name.clone();
            v_flex()
                .gap_3()
                .child(card(
                    format!("Configure {}", integration.display_name),
                    v_flex()
                        .gap_3()
                        .child(ui::kv_row("Name", integration.name.clone()))
                        .child(ui::kv_row("Auth", integration.auth_style.clone()))
                        .child(ui::kv_row("Configured", integration.configured.to_string()))
                        .child(ui::kv_row("Last test", integration_last_text(integration)))
                        .child(fields)
                        .child(
                            h_flex()
                                .gap_2()
                                .flex_wrap()
                                .child(
                                    Button::new(save_label)
                                        .primary()
                                        .small()
                                        .label(if saving { "Saving..." } else { "Save" })
                                        .on_click(move |_, window, cx| {
                                            let _ = save_app.update(cx, |state, cx| {
                                                state.save_integration_credentials(window, cx);
                                            });
                                        }),
                                )
                                .child(
                                    Button::new(test_label)
                                        .small()
                                        .label(if testing { "Testing..." } else { "Test" })
                                        .on_click(move |_, _, cx| {
                                            let _ = test_app.update(cx, |state, cx| {
                                                let name = test_name.clone();
                                                let label = format!("test-integration-{name}");
                                                state.run_api(
                                                    label,
                                                    cx,
                                                    move |client| client.test_integration(&name),
                                                    |state, result, cx| {
                                                        state.set_result_banner(
                                                            &result,
                                                            "Integration test complete.",
                                                        );
                                                        state.refresh_integrations(cx);
                                                    },
                                                );
                                            });
                                        }),
                                )
                                .child(
                                    Button::new(clear_label)
                                        .small()
                                        .danger()
                                        .label(if clearing { "Clearing..." } else { "Clear" })
                                        .on_click(move |_, window, cx| {
                                            let _ = clear_app.update(cx, |state, cx| {
                                                state.clear_integration_credentials(window, cx);
                                            });
                                        }),
                                ),
                        ),
                ))
                .child(card(
                    "Identity",
                    v_flex()
                        .gap_2()
                        .child(ui::kv_row("Status", integration.status.clone()))
                        .child(ui::kv_row("Docs", integration.docs_url.clone()))
                        .child(if let Some(test) = &integration.last_test {
                            v_flex()
                                .gap_2()
                                .child(ui::kv_row("Tested", test.tested_at.clone()))
                                .child(ui::kv_row(
                                    "Error",
                                    test.error.clone().unwrap_or_else(|| "none".to_owned()),
                                ))
                                .child(if let Some(identity) = &test.identity {
                                    v_flex()
                                        .gap_2()
                                        .child(ui::kv_row(
                                            "Identity",
                                            identity.display_name.clone(),
                                        ))
                                        .child(ui::kv_row("Email", option_text(&identity.email)))
                                        .child(ui::kv_row(
                                            "Workspace",
                                            option_text(&identity.workspace),
                                        ))
                                        .into_any_element()
                                } else {
                                    div().into_any_element()
                                })
                                .into_any_element()
                        } else {
                            small_text("No test result yet.").into_any_element()
                        }),
                ))
        } else {
            v_flex().child(card(
                "Configure",
                ui::empty_state(
                    IconName::Network,
                    "No integration selected",
                    "Select an integration to configure credentials.",
                ),
            ))
        };

        let health = card(
            "Integration Health",
            div().flex_1().min_h(px(0.)).overflow_hidden().child(list),
        )
        .w_full()
        .h_full()
        .min_h(px(0.));
        let rail = ui::side_rail()
            .h_full()
            .min_h(px(0.))
            .overflow_hidden()
            .child(
                div()
                    .id("integrations-details-scroll-frame")
                    .size_full()
                    .overflow_y_scrollbar()
                    .pr_1()
                    .child(details),
            );

        h_flex()
            .size_full()
            .min_h(px(0.))
            .items_stretch()
            .gap_4()
            .overflow_hidden()
            .child(ui::content_region().h_full().min_h(px(0.)).child(health))
            .child(rail)
    }

    fn render_config_settings_row(&self, row: ConfigRow, cx: &mut Context<Self>) -> AnyElement {
        let Some(config) = &self.config else {
            return div().into_any_element();
        };
        match row {
            ConfigRow::Group { group } => div()
                .id(format!("config-group-{group}"))
                .w_full()
                .min_h(px(32.))
                .pt_2()
                .pb_1()
                .child(ui::section_title(group, config_group_color(group)))
                .into_any_element(),
            ConfigRow::Field { field } => div()
                .w_full()
                .pb_2()
                .child(self.render_config_field_row(field, config, cx))
                .into_any_element(),
        }
    }

    fn render_config_field_row(
        &self,
        field: &'static ConfigField,
        config: &ConfigSnapshot,
        cx: &mut Context<Self>,
    ) -> AnyElement {
        let selected = self.selected_config_key == field.key;
        let app = cx.entity().downgrade();
        let key = field.key;
        let current_preview = compact_text(&config_value(config, key), 110);
        let editor_color = config_editor_color(field.editor);
        ui::compact_row(selected, editor_color)
            .id(format!("config-field-{}", field.key))
            .min_h(px(68.))
            .on_click(move |_, window, cx| {
                let _ = app.update(cx, |state, cx| {
                    state.open_config_field(key, window, cx);
                });
            })
            .child(ui::icon_badge(config_group_icon(field.group), editor_color))
            .child(
                v_flex()
                    .flex_1()
                    .min_w(px(0.))
                    .overflow_hidden()
                    .gap_1()
                    .child(
                        h_flex()
                            .gap_2()
                            .flex_wrap()
                            .child(ui::row_title(field.label))
                            .child(status_pill(field.editor.label(), editor_color))
                            .child(if field.restart_required {
                                status_pill("restart", rgb(0xf97316))
                            } else {
                                div()
                            }),
                    )
                    .child(ui::row_meta(field.description))
                    .child(ui::row_meta(current_preview)),
            )
            .into_any_element()
    }

    fn render_config_page(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> Div {
        let Some(config) = &self.config else {
            return card("Config", small_text("Config has not loaded yet."));
        };
        let list_state = self.config_list_state.clone();
        let settings_list = list(
            list_state.clone(),
            cx.processor(move |this, index: usize, _window, cx| {
                let row = this.config_rows.get(index).copied();
                row.map(|row| this.render_config_settings_row(row, cx))
                    .unwrap_or_else(|| div().into_any_element())
            }),
        )
        .size_full();

        let settings = card(
            "Settings",
            div()
                .flex_1()
                .min_h(px(0.))
                .overflow_hidden()
                .pr_1()
                .child(settings_list),
        )
        .w_full()
        .h_full()
        .min_h(px(0.));

        let runtime = card(
            "Runtime",
            v_flex()
                .gap_2()
                .child(ui::kv_row("Profile", config.profile.clone()))
                .child(ui::kv_row("Config", config.config_path.clone()))
                .child(ui::kv_row("Vault", config.vault_path.clone()))
                .child(ui::kv_row("Database", config.database_path.clone()))
                .child(ui::kv_row(
                    "Daemon",
                    format!("{}:{}", config.daemon_host, config.daemon_port),
                ))
                .child(ui::kv_row(
                    "LLM",
                    format!("{} / {}", config.llm.provider, config.llm.model),
                ))
                .child(ui::kv_row(
                    "Research",
                    format!(
                        "{} / {}",
                        config.research.provider, config.research.search_mode
                    ),
                ))
                .child(ui::kv_row(
                    "Voice",
                    if config.voice.global_hotkey_enabled {
                        format!(
                            "{} ({})",
                            state_text(&self.dictation_status),
                            config.voice.global_hotkey
                        )
                    } else {
                        "Disabled".to_owned()
                    },
                )),
        )
        .w_full();

        ui::page_columns()
            .h_full()
            .min_h(px(0.))
            .items_stretch()
            .child(ui::content_region().h_full().min_h(px(0.)).child(settings))
            .child(ui::side_rail().h_full().min_h(px(0.)).child(runtime))
    }
}

fn build_config_rows() -> Vec<ConfigRow> {
    let mut rows = Vec::with_capacity(CONFIG_FIELDS.len() + CONFIG_GROUPS.len());
    for group in CONFIG_GROUPS {
        let mut has_group = false;
        for field in CONFIG_FIELDS.iter().filter(|field| field.group == *group) {
            if !has_group {
                rows.push(ConfigRow::Group { group });
                has_group = true;
            }
            rows.push(ConfigRow::Field { field });
        }
    }
    rows
}

fn ordered_task_types(group: &TaskGroup) -> Vec<String> {
    let mut seen = HashSet::new();
    let mut names = Vec::new();
    for name in TASK_TYPE_ORDER {
        if group.contains_key(*name) {
            names.push((*name).to_owned());
            seen.insert((*name).to_owned());
        }
    }
    for name in group.keys() {
        if !seen.contains(name) {
            names.push(name.clone());
        }
    }
    names
}

fn kanban_task_types(group: &TaskGroup) -> Vec<String> {
    let mut seen = HashSet::new();
    let mut names = Vec::new();
    for name in TASK_TYPE_ORDER {
        if group.contains_key(*name) {
            names.push((*name).to_owned());
            seen.insert((*name).to_owned());
        }
    }
    for name in TASK_TYPE_ORDER {
        if !seen.contains(*name) {
            names.push((*name).to_owned());
            seen.insert((*name).to_owned());
        }
    }
    for name in group.keys() {
        if !seen.contains(name) {
            names.push(name.clone());
        }
    }
    names
}

fn value(input: &Entity<InputState>, cx: &mut Context<NinaDesktop>) -> String {
    input.read(cx).value().trim().to_owned()
}

fn non_empty(value: String) -> Option<String> {
    if value.trim().is_empty() {
        None
    } else {
        Some(value)
    }
}

fn card(title: impl Into<String>, body: impl IntoElement) -> Div {
    ui::panel(title, body)
}

fn label(text: impl Into<String>) -> Div {
    ui::label(text)
}

fn small_text(text: impl Into<String>) -> Div {
    ui::small_text(text)
}

fn status_pill(text: impl Into<String>, color: Rgba) -> Div {
    ui::status_pill(text, color)
}

fn meeting_status_color(status: &str) -> Rgba {
    match status {
        "recording" | "failed" | "error" => rgb(0xef4444),
        "completed" | "summarized" | "transcribed" => rgb(0x22c55e),
        _ => rgb(0x38bdf8),
    }
}

fn meeting_duration_text(meeting: &Meeting) -> String {
    meeting
        .duration_seconds
        .map(|duration| format!("{duration:.1}s"))
        .unwrap_or_else(|| "running".to_owned())
}

fn integration_status_color(status: &str) -> Rgba {
    match status {
        "ok" => rgb(0x22c55e),
        "failed" => rgb(0xef4444),
        _ => rgb(0xf97316),
    }
}

fn integration_last_text(integration: &IntegrationRecord) -> String {
    integration
        .last_test
        .as_ref()
        .map(|test| {
            format!(
                "{} - {}ms{}",
                test.status,
                test.latency_ms,
                test.identity
                    .as_ref()
                    .map(|identity| format!(" - {}", identity.display_name))
                    .unwrap_or_default()
            )
        })
        .unwrap_or_else(|| "never tested".to_owned())
}

fn loading_panel(text: &str) -> Div {
    ui::loading_panel(text)
}

fn state_text(text: &str) -> String {
    text.to_owned()
}

fn error_banner(error: ApiError) -> Banner {
    Banner {
        kind: BannerKind::Error,
        text: error.to_string(),
    }
}

fn error_text(text: impl Into<String>) -> Banner {
    Banner {
        kind: BannerKind::Error,
        text: text.into(),
    }
}

fn task_color(task_type: &str) -> Rgba {
    match task_type {
        "coding" => rgb(0x22c55e),
        "reviewing" => rgb(0x38bdf8),
        "research" => rgb(0xeab308),
        "reminder" => rgb(0xf97316),
        "blocked" => rgb(0x94a3b8),
        "done" => rgb(0x22d3ee),
        "unclassified" => rgb(0xa855f7),
        _ => rgb(0x60a5fa),
    }
}

fn role_color(role: &str, fallback: Rgba) -> Rgba {
    match role {
        "user" => rgb(0x60a5fa),
        "assistant" => fallback,
        "tool" => rgb(0xf59e0b),
        _ => rgb(0x94a3b8),
    }
}

fn render_cached_chat_message(message: &RenderedMessage, accent: Rgba) -> Div {
    let role_color = role_color(&message.role, accent);
    let bubble = ui::chat_bubble(message.is_user, role_color)
        .id(format!("message-{}", message.id))
        .child(ui::row_meta(message.meta.clone()))
        .child(match &message.body {
            RenderedMessageBody::Wrapped(paragraphs) => render_cached_wrapped_message(paragraphs),
            RenderedMessageBody::ToolPreview(preview) => render_cached_tool_message(preview),
        });

    let mut row = h_flex().w_full().items_start();
    if message.is_user {
        row = row.justify_end();
    }
    row.child(bubble)
}

fn render_cached_wrapped_message(paragraphs: &[Vec<String>]) -> Div {
    if paragraphs.len() == 1 && paragraphs[0].is_empty() {
        return div().child(ui::small_text("No content."));
    }

    let mut body = v_flex()
        .w_full()
        .min_w(px(0.))
        .overflow_hidden()
        .text_size(px(14.))
        .line_height(relative(1.45))
        .text_color(color::text())
        .gap_2();

    for paragraph in paragraphs {
        if paragraph.is_empty() {
            body = body.child(div().h(px(4.)));
            continue;
        }

        let mut block = v_flex().w_full().gap_1();
        for line in paragraph {
            block = block.child(
                div()
                    .w_full()
                    .min_w(px(0.))
                    .overflow_hidden()
                    .line_height(relative(1.45))
                    .child(line.clone()),
            );
        }
        body = body.child(block);
    }

    body
}

fn render_cached_tool_message(preview: &str) -> Div {
    v_flex()
        .w_full()
        .min_w(px(0.))
        .gap_2()
        .child(status_pill("tool output", color::primary()))
        .child(
            div()
                .w_full()
                .min_w(px(0.))
                .overflow_hidden()
                .font_family("monospace")
                .text_size(px(12.))
                .line_height(relative(1.35))
                .text_color(color::text_muted())
                .child(preview.to_owned()),
        )
}

fn message_label(role: &str) -> &'static str {
    match role {
        "user" => "You",
        "assistant" => "Nina",
        "tool" => "Tool",
        _ => "Message",
    }
}

fn short_timestamp(value: &str) -> String {
    let Some((date, time)) = value.split_once('T') else {
        return compact_text(value, 24);
    };
    let time = time.split(['.', '+']).next().unwrap_or(time);
    format!("{date} {time}")
}

fn wrapped_paragraphs(content: &str, max_chars: usize) -> Vec<Vec<String>> {
    let normalized = content.replace("\r\n", "\n");
    let mut paragraphs = Vec::new();

    for raw in normalized.lines() {
        let paragraph = raw.trim();
        if paragraph.is_empty() {
            paragraphs.push(Vec::new());
        } else {
            paragraphs.push(wrap_line(paragraph, max_chars));
        }
    }

    if paragraphs.is_empty() {
        paragraphs.push(Vec::new());
    }
    paragraphs
}

fn wrap_line(text: &str, max_chars: usize) -> Vec<String> {
    let mut lines = Vec::new();
    let mut current = String::new();

    for word in text.split_whitespace() {
        for segment in split_long_word(word, max_chars) {
            let current_len = current.chars().count();
            let segment_len = segment.chars().count();
            let separator_len = usize::from(!current.is_empty());

            if current_len + separator_len + segment_len > max_chars && !current.is_empty() {
                lines.push(current);
                current = String::new();
            }

            if !current.is_empty() {
                current.push(' ');
            }
            current.push_str(&segment);
        }
    }

    if !current.is_empty() {
        lines.push(current);
    }
    lines
}

fn split_long_word(word: &str, max_chars: usize) -> Vec<String> {
    if max_chars == 0 || word.chars().count() <= max_chars {
        return vec![word.to_owned()];
    }

    let mut segments = Vec::new();
    let mut current = String::new();

    for ch in word.chars() {
        if current.chars().count() >= max_chars {
            segments.push(current);
            current = String::new();
        }
        current.push(ch);
    }

    if !current.is_empty() {
        segments.push(current);
    }
    segments
}

fn tool_preview(content: &str) -> String {
    if let Ok(value) = serde_json::from_str::<Value>(content) {
        if let Some(object) = value.as_object() {
            for key in ["notes", "tasks", "repositories", "results", "items"] {
                if let Some(items) = object.get(key).and_then(Value::as_array) {
                    return format!(
                        "Returned {} {}. {}",
                        items.len(),
                        key,
                        compact_text(content, 260)
                    );
                }
            }
        }
        return compact_text(&value.to_string(), 320);
    }
    compact_text(content, 320)
}

fn compact_text(value: &str, max_chars: usize) -> String {
    let normalized = value.split_whitespace().collect::<Vec<_>>().join(" ");
    if normalized.chars().count() <= max_chars {
        return normalized;
    }
    format!(
        "{}...",
        normalized.chars().take(max_chars).collect::<String>()
    )
}

fn render_task_logs(logs: &CodexTaskLogsResponse) -> Div {
    let body = logs
        .lines
        .iter()
        .rev()
        .take(80)
        .rev()
        .cloned()
        .collect::<Vec<_>>()
        .join("\n");
    card(
        format!("Codex Logs - {}", logs.run_id.as_deref().unwrap_or("none")),
        v_flex()
            .gap_2()
            .child(small_text(logs.path.clone()))
            .child(ui::mono_block(body)),
    )
}

fn option_text(value: &Option<String>) -> String {
    value.clone().unwrap_or_else(|| "never".to_owned())
}

fn config_field(key: &str) -> Option<&'static ConfigField> {
    CONFIG_FIELDS.iter().find(|field| field.key == key)
}

fn config_group_icon(group: &str) -> IconName {
    match group {
        "Storage" => IconName::FolderOpen,
        "Daemon" => IconName::Cpu,
        "LLM" => IconName::Bot,
        "Research" => IconName::Globe,
        "Schedule" => IconName::Calendar,
        "Transcription" => IconName::BookOpen,
        "Meetings" => IconName::Calendar,
        "Voice" => IconName::BookOpen,
        "Codex" => IconName::Cpu,
        _ => IconName::Settings2,
    }
}

fn config_group_color(group: &str) -> Rgba {
    match group {
        "Storage" => rgb(0x38bdf8),
        "Daemon" => rgb(0xf97316),
        "LLM" => rgb(0x22c55e),
        "Research" => rgb(0xeab308),
        "Schedule" => rgb(0x60a5fa),
        "Transcription" => rgb(0xa855f7),
        "Meetings" => rgb(0x22d3ee),
        "Voice" => rgb(0xf43f5e),
        "Codex" => color::primary(),
        _ => color::text_muted(),
    }
}

fn config_editor_color(editor: ConfigEditor) -> Rgba {
    match editor {
        ConfigEditor::Path => rgb(0x38bdf8),
        ConfigEditor::Number => rgb(0x22c55e),
        ConfigEditor::Choice(_) => color::primary(),
        ConfigEditor::Text => color::text_muted(),
    }
}

fn config_option_matches(current: &str, option: &str) -> bool {
    current.trim().eq_ignore_ascii_case(option.trim())
}

fn short_id(value: &str) -> String {
    value.chars().take(8).collect()
}

fn config_value(config: &ConfigSnapshot, key: &str) -> String {
    match key {
        "vault_path" => config.vault_path.clone(),
        "database_path" => config.database_path.clone(),
        "daemon_host" => config.daemon_host.clone(),
        "daemon_port" => config.daemon_port.to_string(),
        "log_level" => config.log_level.clone(),
        "llm.provider" => config.llm.provider.clone(),
        "llm.model" => config.llm.model.clone(),
        "llm.base_url" => config.llm.base_url.clone().unwrap_or_default(),
        "research.provider" => config.research.provider.clone(),
        "research.model" => config.research.model.clone(),
        "research.search_mode" => config.research.search_mode.clone(),
        "research.timeout_seconds" => config.research.timeout_seconds.to_string(),
        "transcription.backend" => config.transcription.backend.clone(),
        "transcription.model" => config.transcription.model.clone(),
        "transcription.device" => config.transcription.device.clone(),
        "transcription.compute_type" => config.transcription.compute_type.clone(),
        "transcription.language" => config
            .transcription
            .language
            .clone()
            .unwrap_or_else(|| "auto".to_owned()),
        "meetings.default_source" => config.meetings.default_source.clone(),
        "meetings.auto_summarize" => config.meetings.auto_summarize.to_string(),
        "meetings.sample_rate" => config.meetings.sample_rate.to_string(),
        "meetings.channels" => config.meetings.channels.to_string(),
        "meetings.default_gain" => config.meetings.default_gain.to_string(),
        "meetings.auto_normalize" => config.meetings.auto_normalize.to_string(),
        "meetings.normalize_target_dbfs" => config.meetings.normalize_target_dbfs.to_string(),
        "meetings.noise_reduction" => config.meetings.noise_reduction.clone(),
        "voice.global_hotkey_enabled" => config.voice.global_hotkey_enabled.to_string(),
        "voice.global_hotkey" => config.voice.global_hotkey.clone(),
        "voice.insert_mode" => config.voice.insert_mode.clone(),
        "voice.preserve_clipboard" => config.voice.preserve_clipboard.to_string(),
        "codex.enabled" => config.codex.enabled.to_string(),
        "codex.binary_path" => config.codex.binary_path.clone(),
        _ => String::new(),
    }
}

fn build_config_patch(key: &str, raw: &str) -> Result<Value, String> {
    let bool_value = || parse_bool(raw);
    let int_value = || {
        raw.parse::<u16>()
            .map_err(|_| format!("{key} must be a number."))
    };
    let float_value = || {
        raw.parse::<f64>()
            .map_err(|_| format!("{key} must be a number."))
    };
    Ok(match key {
        "vault_path" => json!({ "vault_path": raw }),
        "database_path" => json!({ "database_path": raw }),
        "daemon_host" => json!({ "daemon_host": raw }),
        "daemon_port" => json!({ "daemon_port": int_value()? }),
        "log_level" => json!({ "log_level": raw }),
        "llm.provider" => json!({ "llm": { "provider": raw } }),
        "llm.model" => json!({ "llm": { "model": raw } }),
        "llm.base_url" => {
            json!({ "llm": { "base_url": if raw.trim().is_empty() { Value::Null } else { Value::String(raw.trim().to_owned()) } } })
        }
        "research.provider" => json!({ "research": { "provider": raw } }),
        "research.model" => json!({ "research": { "model": raw } }),
        "research.search_mode" => json!({ "research": { "search_mode": raw } }),
        "research.timeout_seconds" => json!({ "research": { "timeout_seconds": float_value()? } }),
        "transcription.backend" => json!({ "transcription": { "backend": raw } }),
        "transcription.model" => json!({ "transcription": { "model": raw } }),
        "transcription.device" => json!({ "transcription": { "device": raw } }),
        "transcription.compute_type" => json!({ "transcription": { "compute_type": raw } }),
        "transcription.language" => {
            json!({ "transcription": { "language": if raw == "auto" { Value::Null } else { Value::String(raw.to_owned()) } } })
        }
        "meetings.default_source" => json!({ "meetings": { "default_source": raw } }),
        "meetings.auto_summarize" => json!({ "meetings": { "auto_summarize": bool_value()? } }),
        "meetings.sample_rate" => json!({ "meetings": { "sample_rate": int_value()? } }),
        "meetings.channels" => json!({ "meetings": { "channels": int_value()? } }),
        "meetings.default_gain" => json!({ "meetings": { "default_gain": float_value()? } }),
        "meetings.auto_normalize" => json!({ "meetings": { "auto_normalize": bool_value()? } }),
        "meetings.normalize_target_dbfs" => {
            json!({ "meetings": { "normalize_target_dbfs": float_value()? } })
        }
        "meetings.noise_reduction" => json!({ "meetings": { "noise_reduction": raw } }),
        "voice.global_hotkey_enabled" => {
            json!({ "voice": { "global_hotkey_enabled": bool_value()? } })
        }
        "voice.global_hotkey" => json!({ "voice": { "global_hotkey": raw } }),
        "voice.insert_mode" => json!({ "voice": { "insert_mode": raw } }),
        "voice.preserve_clipboard" => json!({ "voice": { "preserve_clipboard": bool_value()? } }),
        "codex.enabled" => json!({ "codex": { "enabled": bool_value()? } }),
        "codex.binary_path" => json!({ "codex": { "binary_path": raw } }),
        _ => return Err(format!("Unsupported config field: {key}")),
    })
}

fn parse_bool(raw: &str) -> Result<bool, String> {
    match raw.trim().to_lowercase().as_str() {
        "true" | "1" | "yes" | "on" => Ok(true),
        "false" | "0" | "no" | "off" => Ok(false),
        _ => Err("value must be true or false.".to_owned()),
    }
}

fn split_command(template: &str, path: &str) -> Option<(String, Vec<String>)> {
    let mut parts = template
        .split_whitespace()
        .map(|part| part.replace("{path}", path));
    let binary = parts.next()?;
    Some((binary, parts.collect()))
}
