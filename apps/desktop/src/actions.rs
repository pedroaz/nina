use gpui::{actions, App, KeyBinding};

pub const DESKTOP_CONTEXT: &str = "NinaDesktop";

actions!(nina_desktop, [CloseModal, ClearConversation]);

pub fn bind(cx: &mut App) {
    cx.bind_keys([
        KeyBinding::new("escape", CloseModal, Some(DESKTOP_CONTEXT)),
        KeyBinding::new("ctrl-l", ClearConversation, Some(DESKTOP_CONTEXT)),
    ]);
}
