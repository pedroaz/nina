use std::{
    io::{Read, Write},
    process::{Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    thread,
    time::{Duration, Instant},
};

use crate::{
    api::{ApiClient, ApiError},
    models::{VoiceCapture, VoiceConfig},
};

const SHORTCUT_ID: &str = "nina-global-dictation";
const GLOBAL_DICTATION_TITLE: &str = "Global dictation";
const SHORTCUT_DEBOUNCE_MS: u64 = 700;
const PASTE_FOCUS_DELAY_MS: u64 = 50;
const CLIPBOARD_FAIL_FAST_MS: u64 = 50;
const DICTATION_DESKTOP_NOTIFICATIONS_ENABLED: bool = false;

type SharedDictationStatus = Arc<Mutex<DictationStatus>>;

struct TimingTrace {
    label: &'static str,
    started_at: Instant,
    last_at: Instant,
}

impl TimingTrace {
    fn new(label: &'static str) -> Self {
        let now = Instant::now();
        Self {
            label,
            started_at: now,
            last_at: now,
        }
    }

    fn log(&mut self, message: impl AsRef<str>) {
        let now = Instant::now();
        let elapsed = now.duration_since(self.started_at).as_millis();
        let step = now.duration_since(self.last_at).as_millis();
        self.last_at = now;
        eprintln!(
            "[nina] {} +{}ms (+{}ms): {}",
            self.label,
            elapsed,
            step,
            message.as_ref(),
        );
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct DictationKey {
    hotkey: String,
    insert_mode: String,
    preserve_clipboard: bool,
}

#[derive(Debug, Clone)]
struct DictationStatus {
    state: String,
    detail: Option<String>,
    last_error: Option<String>,
}

impl DictationStatus {
    fn disabled() -> Self {
        Self {
            state: "Disabled".to_owned(),
            detail: None,
            last_error: None,
        }
    }

    fn text(&self) -> String {
        match (&self.detail, &self.last_error) {
            (Some(detail), Some(error)) => format!("{}: {} ({})", self.state, detail, error),
            (Some(detail), None) => format!("{}: {}", self.state, detail),
            (None, Some(error)) => format!("{}: {}", self.state, error),
            (None, None) => self.state.clone(),
        }
    }
}

pub struct GlobalDictationController {
    key: Option<DictationKey>,
    stop_flag: Option<Arc<AtomicBool>>,
    status: SharedDictationStatus,
}

impl GlobalDictationController {
    pub fn new() -> Self {
        Self {
            key: None,
            stop_flag: None,
            status: Arc::new(Mutex::new(DictationStatus::disabled())),
        }
    }

    pub fn status_text(&self) -> String {
        self.status
            .lock()
            .map(|status| status.text())
            .unwrap_or_else(|_| "Unavailable: status lock failed".to_owned())
    }

    pub fn sync(&mut self, config: &VoiceConfig, client: ApiClient) -> String {
        if !config.global_hotkey_enabled {
            self.stop();
            set_status(&self.status, "Disabled", None, None);
            return self.status_text();
        }
        if config.insert_mode != "clipboard_paste" {
            self.stop();
            set_status(
                &self.status,
                "Unavailable",
                Some(format!("Unsupported insert mode: {}", config.insert_mode)),
                None,
            );
            return self.status_text();
        }

        let key = DictationKey {
            hotkey: config.global_hotkey.clone(),
            insert_mode: config.insert_mode.clone(),
            preserve_clipboard: config.preserve_clipboard,
        };
        if self.key.as_ref() == Some(&key) {
            return self.status_text();
        }

        self.stop();
        set_status(&self.status, "Registering", Some(key.hotkey.clone()), None);
        let stop_flag = Arc::new(AtomicBool::new(false));
        start_listener(key.clone(), client, stop_flag.clone(), self.status.clone());
        self.key = Some(key);
        self.stop_flag = Some(stop_flag);
        self.status_text()
    }

    pub fn pause(&mut self, detail: String) -> String {
        self.stop();
        set_status(&self.status, "Paused", Some(detail), None);
        self.status_text()
    }

    pub fn unavailable(&mut self, detail: String) -> String {
        self.stop();
        set_status(&self.status, "Unavailable", Some(detail), None);
        self.status_text()
    }

    fn stop(&mut self) {
        if let Some(flag) = self.stop_flag.take() {
            flag.store(true, Ordering::SeqCst);
        }
        self.key = None;
    }
}

impl Drop for GlobalDictationController {
    fn drop(&mut self) {
        self.stop();
    }
}

fn set_status(
    status: &SharedDictationStatus,
    state: impl Into<String>,
    detail: Option<String>,
    last_error: Option<String>,
) {
    if let Ok(mut current) = status.lock() {
        current.state = state.into();
        current.detail = detail;
        current.last_error = last_error;
    }
}

fn maybe_notify_dictation_event(title: &str, body: &str, high_priority: bool) {
    if DICTATION_DESKTOP_NOTIFICATIONS_ENABLED {
        notify_dictation_event(title, body, high_priority);
    }
}

#[cfg(target_os = "linux")]
fn notify_dictation_event(title: &str, body: &str, high_priority: bool) {
    let title = title.to_owned();
    let body = body.to_owned();
    let _ = thread::Builder::new()
        .name("nina-dictation-notification".to_owned())
        .spawn(move || {
            if send_notify_send(&title, &body, high_priority).is_ok() {
                return;
            }
            let _ = async_io::block_on(async move {
                use ashpd::desktop::notification::{Notification, NotificationProxy, Priority};

                let proxy = NotificationProxy::new().await?;
                let priority = if high_priority {
                    Priority::High
                } else {
                    Priority::Normal
                };
                proxy
                    .add_notification(
                        "nina-global-dictation-status",
                        Notification::new(&title)
                            .body(body.as_str())
                            .priority(priority),
                    )
                    .await?;
                Ok::<(), ashpd::Error>(())
            });
        });
}

#[cfg(target_os = "linux")]
fn send_notify_send(title: &str, body: &str, high_priority: bool) -> Result<(), String> {
    let urgency = if high_priority { "critical" } else { "normal" };
    let args = [
        "--app-name=Nina",
        "--icon=nina",
        "--urgency",
        urgency,
        title,
        body,
    ];
    run_command("notify-send", &args)
}

#[cfg(not(target_os = "linux"))]
fn notify_dictation_event(_title: &str, _body: &str, _high_priority: bool) {}

#[cfg(target_os = "linux")]
fn start_listener(
    key: DictationKey,
    client: ApiClient,
    stop_flag: Arc<AtomicBool>,
    status: SharedDictationStatus,
) {
    let status_for_error = status.clone();
    let _ = thread::Builder::new()
        .name("nina-global-dictation".to_owned())
        .spawn(move || {
            if let Err(err) =
                async_io::block_on(run_portal_listener(key, client, stop_flag, status))
            {
                let message = err.to_string();
                set_status(
                    &status_for_error,
                    "Unavailable",
                    Some("Global shortcut portal failed".to_owned()),
                    Some(message.clone()),
                );
                eprintln!("[nina] global dictation unavailable: {message}");
            }
        });
}

#[cfg(not(target_os = "linux"))]
fn start_listener(
    _key: DictationKey,
    _client: ApiClient,
    _stop_flag: Arc<AtomicBool>,
    status: SharedDictationStatus,
) {
    set_status(
        &status,
        "Unavailable",
        Some("Hotkey is implemented for Linux desktops".to_owned()),
        None,
    );
    eprintln!("[nina] global dictation hotkey is currently implemented for Linux desktops.");
}

#[cfg(target_os = "linux")]
async fn run_portal_listener(
    key: DictationKey,
    client: ApiClient,
    stop_flag: Arc<AtomicBool>,
    status: SharedDictationStatus,
) -> ashpd::Result<()> {
    use ashpd::desktop::{
        global_shortcuts::{BindShortcutsOptions, GlobalShortcuts, NewShortcut},
        CreateSessionOptions,
    };
    use futures_util::{pin_mut, StreamExt as _};

    let proxy = GlobalShortcuts::new().await?;
    let session = proxy
        .create_session(CreateSessionOptions::default())
        .await?;
    let trigger = portal_trigger(&key.hotkey);
    let shortcut = NewShortcut::new(SHORTCUT_ID, "Toggle Nina dictation")
        .preferred_trigger(Some(trigger.as_str()));
    let response = proxy
        .bind_shortcuts(&session, &[shortcut], None, BindShortcutsOptions::default())
        .await?
        .response()?;
    let Some(bound_shortcut) = response
        .shortcuts()
        .iter()
        .find(|shortcut| shortcut.id() == SHORTCUT_ID)
    else {
        set_status(
            &status,
            "Unavailable",
            Some("Global shortcut was not bound".to_owned()),
            None,
        );
        let _ = session.close().await;
        return Ok(());
    };
    let registered_trigger = match bound_shortcut.trigger_description().trim() {
        "" => key.hotkey.clone(),
        trigger => trigger.to_owned(),
    };

    set_status(
        &status,
        "Listening",
        Some(format!("{registered_trigger} registered")),
        None,
    );

    let mut stream = proxy.receive_activated().await?;
    let mut active_capture_id: Option<String> = None;
    let mut last_activation_timestamp: Option<Duration> = None;
    let mut last_activation_seen_at: Option<Instant> = None;
    while !stop_flag.load(Ordering::SeqCst) {
        let next_event = futures_util::FutureExt::fuse(stream.next());
        let timeout =
            futures_util::FutureExt::fuse(async_io::Timer::after(Duration::from_millis(250)));
        pin_mut!(next_event, timeout);
        let event = futures_util::select! {
            event = next_event => event,
            _ = timeout => continue,
        };
        let Some(event) = event else {
            break;
        };
        if event.shortcut_id() != SHORTCUT_ID {
            continue;
        }
        let event_timestamp = event.timestamp();
        let event_seen_at = Instant::now();
        eprintln!(
            "[nina] global dictation activation: timestamp_ms={}",
            event_timestamp.as_millis(),
        );
        if is_duplicate_activation(last_activation_timestamp, event_timestamp)
            || is_duplicate_activation_time(last_activation_seen_at, event_seen_at)
        {
            eprintln!(
                "[nina] global dictation activation ignored: duplicate within {}ms",
                SHORTCUT_DEBOUNCE_MS,
            );
            continue;
        }
        last_activation_timestamp = Some(event_timestamp);
        last_activation_seen_at = Some(event_seen_at);
        set_status(&status, "Activated", Some(key.hotkey.clone()), None);
        if let Err(err) = toggle_dictation(
            &client,
            &mut active_capture_id,
            key.preserve_clipboard,
            &status,
        ) {
            set_status(
                &status,
                "Listening",
                Some("Last activation failed".to_owned()),
                Some(err.clone()),
            );
            maybe_notify_dictation_event(
                "Nina dictation",
                &format!("Global dictation failed: {err}"),
                true,
            );
            eprintln!("[nina] global dictation failed: {err}");
        }
    }

    if let Some(capture_id) = active_capture_id.take() {
        set_status(&status, "Stopping", Some(capture_id.clone()), None);
        let _ = client.stop_voice(&capture_id);
    }
    let _ = session.close().await;
    Ok(())
}

fn is_duplicate_activation(previous: Option<Duration>, current: Duration) -> bool {
    if current == Duration::ZERO {
        return false;
    }
    let Some(previous) = previous else {
        return false;
    };
    let Some(delta) = current.checked_sub(previous) else {
        return false;
    };
    delta < Duration::from_millis(SHORTCUT_DEBOUNCE_MS)
}

fn is_duplicate_activation_time(previous: Option<Instant>, current: Instant) -> bool {
    let Some(previous) = previous else {
        return false;
    };
    let Some(delta) = current.checked_duration_since(previous) else {
        return false;
    };
    delta < Duration::from_millis(SHORTCUT_DEBOUNCE_MS)
}

fn toggle_dictation(
    client: &ApiClient,
    active_capture_id: &mut Option<String>,
    preserve_clipboard: bool,
    status: &SharedDictationStatus,
) -> Result<(), String> {
    if let Some(capture_id) = active_capture_id.take() {
        let mut trace = TimingTrace::new("dictation");
        trace.log(format!("stopping capture {capture_id}"));
        set_status(status, "Stopping", Some(capture_id.clone()), None);
        let stopped = client
            .stop_voice(&capture_id)
            .map_err(|err| err.to_string())?;
        trace.log("recording stop response received");
        if let Some(error) = stopped.error {
            trace.log(format!("recording stop failed: {error}"));
            *active_capture_id = Some(capture_id);
            maybe_notify_dictation_event(
                "Nina dictation",
                &format!("Recording stop failed: {error}"),
                true,
            );
            return Err(error);
        }

        set_status(status, "Transcribing", Some(capture_id.clone()), None);
        trace.log("transcription request start");
        let result = client
            .transcribe_voice(&capture_id, false)
            .map_err(|err| err.to_string())?;
        trace.log(format!(
            "transcription request done chars={}",
            result.transcript.chars().count(),
        ));

        set_status(status, "Pasting", Some(capture_id.clone()), None);
        trace.log("paste start");
        if let Err(error) = paste_transcript(&result.transcript, preserve_clipboard) {
            trace.log(format!("paste failed: {error}"));
            let detail = compact_error(&error, 180);
            eprintln!("[nina] global dictation paste failed: {error}");
            maybe_notify_dictation_event(
                "Nina dictation",
                &format!("Transcript copied. Paste failed: {detail}"),
                true,
            );
            set_status(
                status,
                "Listening",
                Some("Last transcript copied; paste failed".to_owned()),
                Some(error),
            );
            return Ok(());
        }
        trace.log("paste done");
        maybe_notify_dictation_event(
            "Nina dictation",
            "Transcript copied and paste command sent.",
            false,
        );
        set_status(
            status,
            "Listening",
            Some("Last transcript copied".to_owned()),
            None,
        );
        return Ok(());
    }

    if let Some(capture) = recover_active_voice_recording(client) {
        eprintln!(
            "[nina] global dictation recovered active voice recording: {} ({})",
            capture.id, capture.title
        );
        *active_capture_id = Some(capture.id);
        return toggle_dictation(client, active_capture_id, preserve_clipboard, status);
    }

    let capture = match client.record_voice(GLOBAL_DICTATION_TITLE.to_owned()) {
        Ok(capture) => capture,
        Err(err) if is_active_voice_conflict(&err) => {
            eprintln!(
                "[nina] global dictation start found an active voice recording; attempting recovery"
            );
            if let Some(capture) = recover_active_voice_recording(client) {
                eprintln!(
                    "[nina] global dictation recovered active voice recording after conflict: {} ({})",
                    capture.id, capture.title
                );
                *active_capture_id = Some(capture.id);
                return toggle_dictation(client, active_capture_id, preserve_clipboard, status);
            }
            return Err(err.to_string());
        }
        Err(err) => return Err(err.to_string()),
    };
    maybe_notify_dictation_event(
        "Nina dictation",
        "Recording started. Press the hotkey again to stop.",
        true,
    );
    set_status(status, "Recording", Some(capture.id.clone()), None);
    *active_capture_id = Some(capture.id);
    Ok(())
}

fn recover_active_voice_recording(client: &ApiClient) -> Option<VoiceCapture> {
    match client.active_voice() {
        Ok(Some(capture)) if capture.status == "recording" => return Some(capture),
        Ok(_) => {}
        Err(err) => eprintln!("[nina] global dictation active voice lookup failed: {err}"),
    }

    client
        .voice_transcriptions(Some("recording"), 50)
        .ok()?
        .into_iter()
        .map(|item| item.capture)
        .find(|capture| capture.title == GLOBAL_DICTATION_TITLE)
}

fn is_active_voice_conflict(error: &ApiError) -> bool {
    match error {
        ApiError::Status {
            status: 409,
            detail,
        } => detail
            .to_ascii_lowercase()
            .contains("another voice recording is already active"),
        _ => false,
    }
}

fn portal_trigger(raw: &str) -> String {
    let mut modifiers: Vec<&'static str> = Vec::new();
    let mut key = "space".to_owned();
    for part in raw
        .split('+')
        .map(str::trim)
        .filter(|part| !part.is_empty())
    {
        match part.to_ascii_lowercase().as_str() {
            "ctrl" | "control" => push_unique_modifier(&mut modifiers, "CTRL"),
            "alt" | "option" => push_unique_modifier(&mut modifiers, "ALT"),
            "shift" => push_unique_modifier(&mut modifiers, "SHIFT"),
            "super" | "meta" | "cmd" | "command" | "win" | "windows" | "logo" => {
                push_unique_modifier(&mut modifiers, "LOGO")
            }
            "num" | "numlock" => push_unique_modifier(&mut modifiers, "NUM"),
            other => key = xdg_key_identifier(other),
        }
    }
    let mut parts = modifiers.into_iter().map(str::to_owned).collect::<Vec<_>>();
    parts.push(key);
    parts.join("+")
}

fn push_unique_modifier(modifiers: &mut Vec<&'static str>, modifier: &'static str) {
    if !modifiers.contains(&modifier) {
        modifiers.push(modifier);
    }
}

fn xdg_key_identifier(key: &str) -> String {
    match key {
        "space" => "space".to_owned(),
        "enter" | "return" => "Return".to_owned(),
        "esc" | "escape" => "Escape".to_owned(),
        "backspace" => "BackSpace".to_owned(),
        "delete" | "del" => "Delete".to_owned(),
        "tab" => "Tab".to_owned(),
        "left" => "Left".to_owned(),
        "right" => "Right".to_owned(),
        "up" => "Up".to_owned(),
        "down" => "Down".to_owned(),
        "home" => "Home".to_owned(),
        "end" => "End".to_owned(),
        "insert" => "Insert".to_owned(),
        "pageup" | "page_up" => "Page_Up".to_owned(),
        "pagedown" | "page_down" => "Page_Down".to_owned(),
        other if is_function_key(other) => other.to_ascii_uppercase(),
        other if other.len() == 1 => other.to_owned(),
        other => other.to_owned(),
    }
}

fn is_function_key(key: &str) -> bool {
    let Some(number) = key.strip_prefix('f') else {
        return false;
    };
    !number.is_empty() && number.chars().all(|ch| ch.is_ascii_digit())
}

fn paste_transcript(text: &str, preserve_clipboard: bool) -> Result<(), String> {
    let mut trace = TimingTrace::new("paste");
    if text.trim().is_empty() {
        trace.log("skipped empty transcript");
        return Ok(());
    }
    trace.log(format!(
        "start chars={} preserve_clipboard={} session={} wayland_display={} display={}",
        text.chars().count(),
        preserve_clipboard,
        env_value("XDG_SESSION_TYPE"),
        env_value("WAYLAND_DISPLAY"),
        env_value("DISPLAY"),
    ));
    if preserve_clipboard {
        trace.log(
            "clipboard preservation skipped for desktop auto-paste; transcript will remain on clipboard",
        );
    }

    trace.log("writing transcript to Wayland clipboard with wl-copy");
    write_clipboard(text, Some(&mut trace)).map_err(|err| {
        trace.log(format!("clipboard write failed: {err}"));
        err
    })?;
    trace.log("clipboard write accepted");
    trace.log(format!(
        "waiting {}ms for focus/clipboard before focused-window insertion",
        PASTE_FOCUS_DELAY_MS,
    ));
    thread::sleep(Duration::from_millis(PASTE_FOCUS_DELAY_MS));
    trace.log("focus/clipboard wait done");

    let paste_result = insert_transcript(text, &mut trace);
    match &paste_result {
        Ok(()) => trace.log("paste/insert command succeeded"),
        Err(err) => trace.log(format!("paste/insert command failed: {err}")),
    }
    paste_result.map_err(|err| format!("transcript copied to clipboard, but paste failed: {err}"))
}

pub fn copy_text_to_clipboard(text: &str) -> Result<(), String> {
    write_clipboard(text, None)
}

fn write_clipboard(text: &str, mut trace: Option<&mut TimingTrace>) -> Result<(), String> {
    let command = ("wl-copy", Vec::<&str>::new());
    trace_log(
        &mut trace,
        format!(
            "trying clipboard write backend: {}",
            format_command(command.0, &command.1),
        ),
    );
    let result = run_clipboard_writer(command.0, &command.1, text, trace.as_deref_mut());
    if result.is_ok() {
        trace_log(
            &mut trace,
            format!("clipboard write backend {} accepted input", command.0),
        );
    }
    result
}

fn run_clipboard_writer(
    binary: &str,
    args: &[&str],
    input: &str,
    mut trace: Option<&mut TimingTrace>,
) -> Result<(), String> {
    trace_log(
        &mut trace,
        format!(
            "spawning clipboard writer: {}",
            format_command(binary, args)
        ),
    );
    let mut child = Command::new(binary)
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|err| err.to_string())?;
    trace_log(&mut trace, "clipboard writer spawned");
    if let Some(mut stdin) = child.stdin.take() {
        trace_log(
            &mut trace,
            format!("writing {} bytes to clipboard writer", input.len()),
        );
        stdin
            .write_all(input.as_bytes())
            .map_err(|err| err.to_string())?;
        trace_log(&mut trace, "clipboard writer stdin closed");
    }
    trace_log(
        &mut trace,
        format!(
            "waiting {}ms for clipboard writer fail-fast check",
            CLIPBOARD_FAIL_FAST_MS
        ),
    );
    thread::sleep(Duration::from_millis(CLIPBOARD_FAIL_FAST_MS));
    trace_log(&mut trace, "clipboard writer fail-fast check start");
    match child.try_wait().map_err(|err| err.to_string())? {
        Some(status) if status.success() => {
            trace_log(
                &mut trace,
                format!("clipboard writer exited quickly with {status}"),
            );
            Ok(())
        }
        Some(status) => {
            let mut stderr = String::new();
            if let Some(mut pipe) = child.stderr.take() {
                let _ = pipe.read_to_string(&mut stderr);
            }
            let message = stderr.trim();
            Err(if message.is_empty() {
                format!("exited with {status}")
            } else {
                message.to_owned()
            })
        }
        None => {
            trace_log(
                &mut trace,
                "clipboard writer still running; continuing in background",
            );
            let binary_name = binary.to_owned();
            let started_at = trace.as_ref().map(|trace| trace.started_at);
            let _ = thread::Builder::new()
                .name("nina-clipboard-writer".to_owned())
                .spawn(move || match child.wait_with_output() {
                    Ok(output) if output.status.success() => {
                        log_background_paste(
                            started_at,
                            format!("clipboard writer {binary_name} exited successfully"),
                        );
                    }
                    Ok(output) => {
                        let message = String::from_utf8_lossy(&output.stderr).trim().to_owned();
                        if message.is_empty() {
                            log_background_paste(
                                started_at,
                                format!(
                                    "clipboard writer {binary_name} exited with {}",
                                    output.status,
                                ),
                            );
                        } else {
                            log_background_paste(
                                started_at,
                                format!("clipboard writer {binary_name} exited: {message}"),
                            );
                        }
                    }
                    Err(err) => {
                        log_background_paste(
                            started_at,
                            format!("clipboard writer {binary_name} wait failed: {err}"),
                        );
                    }
                });
            Ok(())
        }
    }
}

fn insert_transcript(text: &str, trace: &mut TimingTrace) -> Result<(), String> {
    trace
        .log("trying focused-window text insertion: ydotool type --delay 0 --key-delay 4 --file -");
    run_with_stdin(
        "ydotool",
        &["type", "--delay", "0", "--key-delay", "4", "--file", "-"],
        text,
        trace,
    )
    .map(|()| {
        trace.log("focused-window text insertion ydotool succeeded");
    })
    .map_err(|err| format!("ydotool type failed: {err}"))
}

fn run_with_stdin(
    binary: &str,
    args: &[&str],
    input: &str,
    trace: &mut TimingTrace,
) -> Result<(), String> {
    trace.log(format!(
        "spawning stdin command: {}",
        format_command(binary, args),
    ));
    let mut child = Command::new(binary)
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|err| err.to_string())?;
    trace.log("stdin command spawned");
    if let Some(mut stdin) = child.stdin.take() {
        trace.log(format!("writing {} bytes to stdin command", input.len()));
        stdin
            .write_all(input.as_bytes())
            .map_err(|err| err.to_string())?;
        trace.log("stdin command input sent");
    }
    trace.log("waiting for stdin command exit");
    let output = child.wait_with_output().map_err(|err| err.to_string())?;
    trace.log(format!("stdin command exited with {}", output.status));
    if output.status.success() {
        return Ok(());
    }
    let message = String::from_utf8_lossy(&output.stderr).trim().to_owned();
    Err(if message.is_empty() {
        format!("exited with {}", output.status)
    } else {
        message
    })
}

fn trace_log(trace: &mut Option<&mut TimingTrace>, message: impl AsRef<str>) {
    if let Some(trace) = trace.as_mut() {
        (**trace).log(message);
    }
}

fn log_background_paste(started_at: Option<Instant>, message: impl AsRef<str>) {
    if let Some(started_at) = started_at {
        eprintln!(
            "[nina] paste +{}ms: {}",
            started_at.elapsed().as_millis(),
            message.as_ref(),
        );
    } else {
        eprintln!("[nina] paste: {}", message.as_ref());
    }
}

fn env_value(name: &str) -> String {
    std::env::var(name).unwrap_or_else(|_| "<unset>".to_owned())
}

fn format_command(binary: &str, args: &[&str]) -> String {
    let mut parts = Vec::with_capacity(args.len() + 1);
    parts.push(binary.to_owned());
    parts.extend(args.iter().map(|arg| (*arg).to_owned()));
    parts.join(" ")
}

fn compact_error(error: &str, max_chars: usize) -> String {
    let mut compact = error.split_whitespace().collect::<Vec<_>>().join(" ");
    if compact.chars().count() <= max_chars {
        return compact;
    }
    compact = compact.chars().take(max_chars.saturating_sub(3)).collect();
    compact.push_str("...");
    compact
}

fn run_command(binary: &str, args: &[&str]) -> Result<(), String> {
    let output = Command::new(binary)
        .args(args)
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .output()
        .map_err(|err| err.to_string())?;
    if output.status.success() {
        return Ok(());
    }
    let message = String::from_utf8_lossy(&output.stderr).trim().to_owned();
    Err(if message.is_empty() {
        format!("exited with {}", output.status)
    } else {
        message
    })
}
