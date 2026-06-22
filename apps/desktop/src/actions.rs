use gpui::{actions, App, KeyBinding};

pub const DESKTOP_CONTEXT: &str = "NinaDesktop";

actions!(nina_desktop, [ToggleSidebar, CloseModal, ClearConversation]);

pub fn bind(cx: &mut App) {
    cx.bind_keys([
        KeyBinding::new("ctrl-b", ToggleSidebar, None),
        KeyBinding::new("escape", CloseModal, Some(DESKTOP_CONTEXT)),
        KeyBinding::new("ctrl-l", ClearConversation, Some(DESKTOP_CONTEXT)),
    ]);
}
