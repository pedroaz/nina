use gpui::InteractiveElement as _;
use gpui::*;
use gpui_component::{
    h_flex, scroll::ScrollableElement, theme::ThemeTokens, v_flex, Icon, IconName, Sizable, Theme,
};

pub mod color {
    use gpui::{rgb, Rgba};

    pub fn app_bg() -> Rgba {
        rgb(0x0b0f14)
    }

    pub fn sidebar_bg() -> Rgba {
        rgb(0x10151c)
    }

    pub fn sidebar_border() -> Rgba {
        rgb(0x222b36)
    }

    pub fn sidebar_item_hover() -> Rgba {
        rgb(0x18202a)
    }

    pub fn sidebar_item_active() -> Rgba {
        rgb(0x161d25)
    }

    pub fn surface() -> Rgba {
        rgb(0x151a20)
    }

    pub fn surface_raised() -> Rgba {
        rgb(0x171f28)
    }

    pub fn surface_hover() -> Rgba {
        rgb(0x1b2430)
    }

    pub fn border() -> Rgba {
        rgb(0x2a3038)
    }

    pub fn text() -> Rgba {
        rgb(0xe5e7eb)
    }

    pub fn text_muted() -> Rgba {
        rgb(0x94a3b8)
    }

    pub fn text_faint() -> Rgba {
        rgb(0x64748b)
    }

    pub fn accent() -> Rgba {
        primary()
    }

    pub fn accent_soft() -> Rgba {
        surface_hover()
    }

    pub fn brand_orange() -> Rgba {
        rgb(0xf5a623)
    }

    pub fn primary() -> Rgba {
        brand_orange()
    }

    pub fn primary_hover() -> Rgba {
        rgb(0xffb743)
    }

    pub fn primary_active() -> Rgba {
        rgb(0xd98a12)
    }

    pub fn primary_foreground() -> Rgba {
        rgb(0x121212)
    }

    pub fn primary_soft() -> Rgba {
        rgb(0x1a2028)
    }

    pub fn primary_soft_hover() -> Rgba {
        rgb(0x202936)
    }

    pub fn primary_soft_active() -> Rgba {
        rgb(0x25303c)
    }

    pub fn success() -> Rgba {
        rgb(0x22c55e)
    }

    pub fn warning() -> Rgba {
        rgb(0xf59e0b)
    }

    pub fn danger() -> Rgba {
        rgb(0xef4444)
    }

    pub fn info() -> Rgba {
        rgb(0x38bdf8)
    }

    pub fn neutral() -> Rgba {
        text_faint()
    }
}

pub fn apply_nina_theme(cx: &mut App) {
    let theme = Theme::global_mut(cx);
    let primary = Hsla::from(color::primary());
    let primary_hover = Hsla::from(color::primary_hover());
    let primary_active = Hsla::from(color::primary_active());
    let primary_foreground = Hsla::from(color::primary_foreground());
    let primary_soft = Hsla::from(color::primary_soft());
    let primary_soft_hover = Hsla::from(color::primary_soft_hover());
    let primary_soft_active = Hsla::from(color::primary_soft_active());

    theme.primary = primary;
    theme.primary_hover = primary_hover;
    theme.primary_active = primary_active;
    theme.primary_foreground = primary_foreground;
    theme.button_primary = primary;
    theme.button_primary_hover = primary_hover;
    theme.button_primary_active = primary_active;
    theme.button_primary_foreground = primary_foreground;
    theme.button_active = primary_soft_active;
    theme.button_hover = primary_soft_hover;
    theme.ring = primary;
    theme.selection = Hsla::from(rgba(0xf5a62333));
    theme.sidebar_primary = primary_soft;
    theme.sidebar_primary_foreground = primary;
    theme.link = primary;
    theme.link_hover = primary_hover;
    theme.link_active = primary_active;
    theme.tokens = ThemeTokens::from(&theme.colors);
}

pub fn app_root() -> Div {
    div()
        .size_full()
        .relative()
        .overflow_hidden()
        .bg(color::app_bg())
        .text_color(color::text())
        .font_family("Inter")
}

pub fn page_workspace_frame(content: impl IntoElement) -> Div {
    div()
        .flex_1()
        .min_h(px(0.))
        .overflow_hidden()
        .p_4()
        .child(content)
}

pub fn sidebar_scroll_frame(content: impl IntoElement) -> Div {
    div().flex_1().min_h(px(0.)).overflow_hidden().child(
        div()
            .id("sidebar-scroll-frame")
            .size_full()
            .overflow_y_scrollbar()
            .pr_2()
            .child(content),
    )
}

pub fn panel(title: impl Into<String>, body: impl IntoElement) -> Div {
    v_flex()
        .gap_3()
        .p_4()
        .rounded(px(8.))
        .border_1()
        .border_color(color::border())
        .bg(color::surface())
        .child(
            div()
                .text_size(px(15.))
                .font_weight(FontWeight::SEMIBOLD)
                .child(title.into()),
        )
        .child(body)
}

pub fn label(text: impl Into<String>) -> Div {
    div()
        .text_size(px(12.))
        .text_color(color::text_muted())
        .child(text.into())
}

pub fn section_title(text: impl Into<String>, color: Rgba) -> Div {
    div()
        .font_weight(FontWeight::SEMIBOLD)
        .text_color(color)
        .child(text.into())
}

pub fn small_text(text: impl Into<String>) -> Div {
    div()
        .text_size(px(12.))
        .text_color(color::text_muted())
        .child(text.into())
}

pub fn status_pill(text: impl Into<String>, accent: Rgba) -> Div {
    div()
        .px_2()
        .py_1()
        .rounded(px(999.))
        .border_1()
        .border_color(color::border())
        .bg(color::surface_raised())
        .text_size(px(12.))
        .text_color(accent)
        .child(text.into())
}

pub fn loading_panel(text: &str) -> Div {
    div().p_3().child(small_text(text))
}

pub fn page_columns() -> Div {
    h_flex().w_full().items_start().gap_4().flex_wrap()
}

pub fn page_stack() -> Div {
    v_flex().w_full().gap_4()
}

pub fn side_rail() -> Div {
    v_flex().w(px(380.)).min_w(px(320.)).gap_3().flex_shrink_0()
}

pub fn task_workspace() -> Div {
    h_flex()
        .size_full()
        .min_h(px(0.))
        .items_stretch()
        .gap_4()
        .overflow_hidden()
}

pub fn task_board_surface(body: impl IntoElement) -> Div {
    v_flex()
        .flex_1()
        .h_full()
        .min_w(px(520.))
        .min_h(px(0.))
        .gap_3()
        .p_4()
        .rounded(px(8.))
        .border_1()
        .border_color(color::border())
        .bg(color::surface())
        .child(
            div()
                .text_size(px(15.))
                .font_weight(FontWeight::SEMIBOLD)
                .child("Task Board"),
        )
        .child(body)
}

pub fn task_board_scroll(content: impl IntoElement) -> Div {
    div().flex_1().min_h(px(0.)).overflow_hidden().child(
        div()
            .id("task-board-scroll-frame")
            .size_full()
            .overflow_x_scrollbar()
            .child(content),
    )
}

pub fn modal_overlay(content: impl IntoElement) -> Div {
    div()
        .absolute()
        .inset_0()
        .bg(gpui::rgba(0x00000099))
        .flex()
        .items_center()
        .justify_center()
        .p_6()
        .child(content)
}

pub fn modal_window(content: impl IntoElement) -> Div {
    v_flex()
        .w(px(620.))
        .max_w(relative(0.92))
        .max_h(relative(0.88))
        .overflow_hidden()
        .rounded(px(8.))
        .border_1()
        .border_color(color::border())
        .bg(color::surface())
        .shadow_lg()
        .child(content)
}

pub fn modal_header(title: impl Into<String>, close: impl IntoElement) -> Div {
    h_flex()
        .justify_between()
        .gap_3()
        .px_4()
        .py_3()
        .border_b_1()
        .border_color(color::border())
        .child(
            div()
                .text_size(px(16.))
                .font_weight(FontWeight::SEMIBOLD)
                .child(title.into()),
        )
        .child(close)
}

pub fn modal_body(content: impl IntoElement) -> impl IntoElement {
    div()
        .id("modal-body-scroll-frame")
        .max_h(relative(0.76))
        .overflow_y_scrollbar()
        .p_4()
        .child(content)
}

pub fn content_region() -> Div {
    v_flex().flex_1().min_w(px(520.)).gap_3()
}

pub fn surface_block() -> Div {
    v_flex()
        .gap_3()
        .p_4()
        .rounded(px(8.))
        .border_1()
        .border_color(color::border())
        .bg(color::surface())
}

pub fn empty_state(icon: IconName, title: impl Into<String>, detail: impl Into<String>) -> Div {
    v_flex()
        .w_full()
        .items_center()
        .justify_center()
        .gap_2()
        .p_6()
        .rounded(px(8.))
        .border_1()
        .border_color(color::border())
        .bg(color::surface())
        .child(icon_badge(icon, color::text_faint()))
        .child(
            div()
                .text_size(px(15.))
                .font_weight(FontWeight::SEMIBOLD)
                .child(title.into()),
        )
        .child(
            div()
                .max_w(px(380.))
                .text_align(gpui::TextAlign::Center)
                .child(small_text(detail.into())),
        )
}

pub fn sidebar_shell(collapsed: bool) -> Div {
    let width = if collapsed { px(72.) } else { px(256.) };
    v_flex()
        .w(width)
        .h_full()
        .min_h(px(0.))
        .overflow_hidden()
        .p_3()
        .gap_3()
        .border_r_1()
        .border_color(color::sidebar_border())
        .bg(color::sidebar_bg())
        .flex_shrink_0()
}

pub fn sidebar_brand(collapsed: bool) -> Div {
    let mark = div()
        .size(px(36.))
        .rounded(px(8.))
        .bg(color::primary_soft())
        .border_1()
        .border_color(color::brand_orange())
        .flex()
        .items_center()
        .justify_center()
        .child(
            svg()
                .path("icons/nina.svg")
                .size(px(24.))
                .text_color(color::brand_orange()),
        );

    if collapsed {
        v_flex().items_center().gap_2().child(mark)
    } else {
        h_flex()
            .h(px(44.))
            .justify_between()
            .gap_2()
            .child(mark)
            .child(
                v_flex()
                    .flex_1()
                    .gap_1()
                    .child(
                        div()
                            .text_lg()
                            .font_weight(FontWeight::SEMIBOLD)
                            .child("Nina"),
                    )
                    .child(small_text("Local operations")),
            )
    }
}

pub fn sidebar_item(
    label: impl Into<String>,
    description: impl Into<String>,
    icon: IconName,
    active: bool,
    collapsed: bool,
) -> Div {
    let label = label.into();
    let description = description.into();
    let fg = if active {
        color::text()
    } else {
        color::text_muted()
    };
    let icon_bg = if active {
        color::primary_soft_active()
    } else {
        color::surface_raised()
    };
    let icon_fg = if active { color::primary() } else { fg };
    let icon_cell = div()
        .size(px(30.))
        .rounded(px(7.))
        .bg(icon_bg)
        .flex()
        .items_center()
        .justify_center()
        .flex_shrink_0()
        .child(Icon::new(icon).small().text_color(icon_fg));

    let mut item = h_flex()
        .w_full()
        .min_h(px(44.))
        .gap_2()
        .px_2()
        .py_2()
        .rounded(px(8.))
        .border_1()
        .border_color(if active {
            color::primary()
        } else {
            color::sidebar_bg()
        })
        .bg(if active {
            color::sidebar_item_active()
        } else {
            color::sidebar_bg()
        })
        .text_color(fg)
        .cursor_pointer()
        .hover(|this| {
            this.bg(if active {
                color::sidebar_item_active()
            } else {
                color::sidebar_item_hover()
            })
        });

    if collapsed {
        item = item.justify_center().child(icon_cell);
    } else {
        item = item.child(icon_cell).child(
            v_flex()
                .flex_1()
                .overflow_hidden()
                .gap_1()
                .child(
                    div()
                        .text_size(px(14.))
                        .font_weight(if active {
                            FontWeight::SEMIBOLD
                        } else {
                            FontWeight::NORMAL
                        })
                        .child(label),
                )
                .child(
                    div()
                        .text_size(px(11.))
                        .text_color(color::text_faint())
                        .child(description),
                ),
        );
    }

    item
}

pub fn compact_row(selected: bool, _accent: Rgba) -> Div {
    h_flex()
        .w_full()
        .min_h(px(52.))
        .gap_3()
        .px_3()
        .py_2()
        .rounded(px(8.))
        .border_1()
        .border_color(if selected {
            color::primary()
        } else {
            color::border()
        })
        .bg(if selected {
            color::accent_soft()
        } else {
            color::surface()
        })
        .text_color(if selected {
            color::text()
        } else {
            color::text_muted()
        })
        .cursor_pointer()
        .hover(|this| {
            this.bg(if selected {
                color::primary_soft_hover()
            } else {
                color::surface_hover()
            })
        })
}

pub fn kanban_virtual_lane(
    title: impl Into<String>,
    count: usize,
    color: Rgba,
    body: impl IntoElement,
) -> Div {
    v_flex()
        .w(px(280.))
        .min_w(px(280.))
        .h_full()
        .min_h(px(0.))
        .gap_3()
        .p_3()
        .rounded(px(8.))
        .border_1()
        .border_color(color::border())
        .bg(color::surface_raised())
        .child(
            h_flex()
                .justify_between()
                .child(section_title(title.into(), color))
                .child(status_pill(count.to_string(), color)),
        )
        .child(div().flex_1().min_h(px(0.)).overflow_hidden().child(body))
}

pub fn kanban_card(selected: bool, _accent: Rgba) -> Div {
    v_flex()
        .w_full()
        .gap_2()
        .p_3()
        .rounded(px(8.))
        .border_1()
        .border_color(if selected {
            color::primary()
        } else {
            color::border()
        })
        .bg(if selected {
            color::accent_soft()
        } else {
            color::surface()
        })
        .text_color(if selected {
            color::text()
        } else {
            color::text_muted()
        })
        .cursor_pointer()
        .hover(|this| {
            this.bg(if selected {
                color::primary_soft_hover()
            } else {
                color::surface_hover()
            })
        })
}

pub fn chat_canvas() -> Div {
    v_flex()
        .size_full()
        .min_h(px(0.))
        .w_full()
        .max_w(px(1080.))
        .gap_3()
        .mx_auto()
}

pub fn chat_history() -> Div {
    v_flex()
        .w_full()
        .flex_1()
        .min_h(px(0.))
        .rounded(px(8.))
        .border_1()
        .border_color(color::border())
        .bg(color::surface())
        .overflow_hidden()
}

pub fn chat_bubble(is_user: bool, accent: Rgba) -> Div {
    let width = if is_user { px(520.) } else { px(720.) };

    v_flex()
        .w(width)
        .max_w(relative(0.78))
        .min_w(px(0.))
        .gap_2()
        .p_3()
        .rounded(px(8.))
        .border_1()
        .border_color(if is_user { color::primary() } else { accent })
        .bg(if is_user {
            color::accent_soft()
        } else {
            color::surface_raised()
        })
        .overflow_hidden()
}

pub fn chat_composer() -> Div {
    v_flex()
        .w_full()
        .flex_shrink_0()
        .gap_3()
        .p_3()
        .rounded(px(8.))
        .border_1()
        .border_color(color::border())
        .bg(color::surface())
}

pub fn kv_row(label: impl Into<String>, value: impl Into<String>) -> Div {
    h_flex()
        .w_full()
        .items_start()
        .justify_between()
        .gap_3()
        .child(
            div()
                .min_w(px(120.))
                .flex_shrink_0()
                .text_size(px(12.))
                .text_color(color::text_faint())
                .child(label.into()),
        )
        .child(
            div()
                .flex_1()
                .min_w(px(0.))
                .overflow_hidden()
                .text_size(px(12.))
                .text_color(color::text_muted())
                .child(value.into()),
        )
}

pub fn row_title(text: impl Into<String>) -> Div {
    div()
        .w_full()
        .min_w(px(0.))
        .overflow_hidden()
        .text_size(px(15.))
        .font_weight(FontWeight::MEDIUM)
        .text_color(color::text())
        .child(text.into())
}

pub fn row_meta(text: impl Into<String>) -> Div {
    div()
        .w_full()
        .min_w(px(0.))
        .overflow_hidden()
        .text_size(px(12.))
        .text_color(color::text_muted())
        .child(text.into())
}

pub fn mono_block(text: impl Into<String>) -> Div {
    div()
        .w_full()
        .p_3()
        .rounded(px(8.))
        .border_1()
        .border_color(color::border())
        .bg(color::app_bg())
        .font_family("monospace")
        .text_size(px(12.))
        .text_color(color::text_muted())
        .child(text.into())
}

pub fn icon_badge(icon: IconName, accent: Rgba) -> Div {
    div()
        .size(px(32.))
        .rounded(px(8.))
        .bg(color::surface_raised())
        .border_1()
        .border_color(color::border())
        .flex()
        .items_center()
        .justify_center()
        .flex_shrink_0()
        .child(Icon::new(icon).small().text_color(accent))
}
