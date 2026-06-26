use gpui::{actions, App, KeyBinding};

pub const DESKTOP_CONTEXT: &str = "NinaDesktop";
pub const ASSISTANT_CONTEXT: &str = "NinaAssistant";
const ASSISTANT_INPUT_CONTEXT: &str = "NinaAssistant && Input";

actions!(
    nina_desktop,
    [
        CloseModal,
        ClearConversation,
        OpenAssistant,
        OpenObsidian,
        ToggleAssistantMode,
        SwitchToTasks,
        SwitchToMeetings,
        SwitchToResearch
    ]
);

pub fn bind(cx: &mut App) {
    cx.bind_keys([
        KeyBinding::new("escape", CloseModal, Some(DESKTOP_CONTEXT)),
        KeyBinding::new("ctrl-l", ClearConversation, Some(DESKTOP_CONTEXT)),
        KeyBinding::new("ctrl-b", OpenAssistant, Some(DESKTOP_CONTEXT)),
        KeyBinding::new("ctrl-o", OpenObsidian, Some(DESKTOP_CONTEXT)),
        KeyBinding::new("tab", ToggleAssistantMode, Some(DESKTOP_CONTEXT)),
        KeyBinding::new("tab", ToggleAssistantMode, Some(ASSISTANT_INPUT_CONTEXT)),
        KeyBinding::new("ctrl-t", SwitchToTasks, Some(DESKTOP_CONTEXT)),
        KeyBinding::new("ctrl-e", SwitchToMeetings, Some(DESKTOP_CONTEXT)),
        KeyBinding::new("ctrl-r", SwitchToResearch, Some(DESKTOP_CONTEXT)),
    ]);
}
