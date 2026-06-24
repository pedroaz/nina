use std::{
    io::Write,
    process::{Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    thread,
    time::Duration,
};

use crate::{api::ApiClient, models::VoiceConfig};

const SHORTCUT_ID: &str = "nina-global-dictation";

#[derive(Debug, Clone, PartialEq, Eq)]
struct DictationKey {
    hotkey: String,
    insert_mode: String,
    preserve_clipboard: bool,
}

pub struct GlobalDictationController {
    key: Option<DictationKey>,
    stop_flag: Option<Arc<AtomicBool>>,
}

impl GlobalDictationController {
    pub fn new() -> Self {
        Self {
            key: None,
            stop_flag: None,
        }
    }

    pub fn sync(&mut self, config: &VoiceConfig, client: ApiClient) -> String {
        if !config.global_hotkey_enabled {
            self.stop();
            return "Disabled".to_owned();
        }
        if config.insert_mode != "clipboard_paste" {
            self.stop();
            return format!("Unsupported insert mode: {}", config.insert_mode);
        }

        let key = DictationKey {
            hotkey: config.global_hotkey.clone(),
            insert_mode: config.insert_mode.clone(),
            preserve_clipboard: config.preserve_clipboard,
        };
        if self.key.as_ref() == Some(&key) {
            return "Listening".to_owned();
        }

        self.stop();
        let stop_flag = Arc::new(AtomicBool::new(false));
        start_listener(key.clone(), client, stop_flag.clone());
        self.key = Some(key);
        self.stop_flag = Some(stop_flag);
        "Listening".to_owned()
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

#[cfg(target_os = "linux")]
fn start_listener(key: DictationKey, client: ApiClient, stop_flag: Arc<AtomicBool>) {
    let _ = thread::Builder::new()
        .name("nina-global-dictation".to_owned())
        .spawn(move || {
            if let Err(err) = async_io::block_on(run_portal_listener(key, client, stop_flag)) {
                eprintln!("[nina] global dictation unavailable: {err}");
            }
        });
}

#[cfg(not(target_os = "linux"))]
fn start_listener(_key: DictationKey, _client: ApiClient, _stop_flag: Arc<AtomicBool>) {
    eprintln!("[nina] global dictation hotkey is currently implemented for Linux desktops.");
}

#[cfg(target_os = "linux")]
async fn run_portal_listener(
    key: DictationKey,
    client: ApiClient,
    stop_flag: Arc<AtomicBool>,
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
    proxy
        .bind_shortcuts(&session, &[shortcut], None, BindShortcutsOptions::default())
        .await?
        .response()?;

    let mut stream = proxy.receive_activated().await?;
    let mut active_capture_id: Option<String> = None;
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
        if let Err(err) = toggle_dictation(&client, &mut active_capture_id, key.preserve_clipboard)
        {
            eprintln!("[nina] global dictation failed: {err}");
        }
    }

    if let Some(capture_id) = active_capture_id.take() {
        let _ = client.stop_voice(&capture_id);
    }
    let _ = session.close().await;
    Ok(())
}

fn toggle_dictation(
    client: &ApiClient,
    active_capture_id: &mut Option<String>,
    preserve_clipboard: bool,
) -> Result<(), String> {
    if let Some(capture_id) = active_capture_id.take() {
        let stopped = client
            .stop_voice(&capture_id)
            .map_err(|err| err.to_string())?;
        if let Some(error) = stopped.error {
            return Err(error);
        }
        let result = client
            .transcribe_voice(&capture_id, false)
            .map_err(|err| err.to_string())?;
        paste_transcript(&result.transcript, preserve_clipboard)?;
        return Ok(());
    }

    let capture = client
        .record_voice("Global dictation".to_owned())
        .map_err(|err| err.to_string())?;
    *active_capture_id = Some(capture.id);
    Ok(())
}

fn portal_trigger(raw: &str) -> String {
    let mut modifiers = Vec::new();
    let mut key = "space".to_owned();
    for part in raw
        .split('+')
        .map(str::trim)
        .filter(|part| !part.is_empty())
    {
        match part.to_ascii_lowercase().as_str() {
            "ctrl" | "control" => modifiers.push("<Control>"),
            "alt" | "option" => modifiers.push("<Alt>"),
            "shift" => modifiers.push("<Shift>"),
            "super" | "meta" | "cmd" | "command" | "win" | "windows" => modifiers.push("<Super>"),
            "space" => key = "space".to_owned(),
            "enter" | "return" => key = "Return".to_owned(),
            "esc" | "escape" => key = "Escape".to_owned(),
            other => key = other.to_owned(),
        }
    }
    format!("{}{}", modifiers.join(""), key)
}

fn paste_transcript(text: &str, preserve_clipboard: bool) -> Result<(), String> {
    if text.trim().is_empty() {
        return Ok(());
    }
    let previous = if preserve_clipboard {
        read_clipboard()
    } else {
        None
    };
    write_clipboard(text)?;
    if let Err(err) = send_paste_shortcut() {
        eprintln!("[nina] copied dictation transcript but could not paste it: {err}");
    }
    if let Some(previous) = previous {
        thread::spawn(move || {
            thread::sleep(Duration::from_millis(750));
            let _ = write_clipboard(&previous);
        });
    }
    Ok(())
}

fn read_clipboard() -> Option<String> {
    for command in [
        ("wl-paste", vec!["--no-newline"]),
        ("xclip", vec!["-selection", "clipboard", "-out"]),
        ("xsel", vec!["--clipboard", "--output"]),
    ] {
        if let Ok(output) = Command::new(command.0).args(command.1).output() {
            if output.status.success() {
                if let Ok(text) = String::from_utf8(output.stdout) {
                    return Some(text);
                }
            }
        }
    }
    None
}

fn write_clipboard(text: &str) -> Result<(), String> {
    for command in [
        ("wl-copy", Vec::<&str>::new()),
        ("xclip", vec!["-selection", "clipboard"]),
        ("xsel", vec!["--clipboard", "--input"]),
    ] {
        if run_with_stdin(command.0, &command.1, text).is_ok() {
            return Ok(());
        }
    }
    Err("no clipboard writer found; install wl-clipboard on Wayland".to_owned())
}

fn run_with_stdin(binary: &str, args: &[&str], input: &str) -> Result<(), String> {
    let mut child = Command::new(binary)
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|err| err.to_string())?;
    if let Some(stdin) = child.stdin.as_mut() {
        stdin
            .write_all(input.as_bytes())
            .map_err(|err| err.to_string())?;
    }
    let output = child.wait_with_output().map_err(|err| err.to_string())?;
    if output.status.success() {
        Ok(())
    } else {
        Err(String::from_utf8_lossy(&output.stderr).trim().to_owned())
    }
}

fn send_paste_shortcut() -> Result<(), String> {
    if Command::new("wtype")
        .args(["-M", "ctrl", "-P", "v", "-p", "v", "-m", "ctrl"])
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
    {
        return Ok(());
    }
    if Command::new("xdotool")
        .args(["key", "ctrl+v"])
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
    {
        return Ok(());
    }
    Err("no paste automation command found; install wtype on Wayland".to_owned())
}
