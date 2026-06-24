mod actions;
mod api;
mod app;
mod assets;
mod dictation;
mod models;
mod ui;

use anyhow::Result;
use app::NinaDesktop;
use gpui::*;
use gpui_component::{Root, Theme, ThemeMode};

fn startup_window_bounds() -> WindowBounds {
    WindowBounds::Maximized(Bounds::new(
        point(px(80.), px(80.)),
        size(px(1440.), px(900.)),
    ))
}

fn main() -> Result<()> {
    gpui_platform::application()
        .with_assets(assets::DesktopAssets)
        .run(move |cx| {
            gpui_component::init(cx);
            Theme::change(ThemeMode::Dark, None, cx);
            ui::apply_nina_theme(cx);
            actions::bind(cx);
            cx.spawn(async move |cx| {
                cx.open_window(
                    WindowOptions {
                        app_id: Some("nina".to_owned()),
                        window_bounds: Some(startup_window_bounds()),
                        icon: assets::window_icon(),
                        ..WindowOptions::default()
                    },
                    |window, cx| {
                        let view = cx.new(|cx| NinaDesktop::new(window, cx));
                        cx.new(|cx| Root::new(view, window, cx))
                    },
                )
                .map_err(|err| anyhow::anyhow!("failed to open Nina Desktop: {err}"))?;
                Ok::<_, anyhow::Error>(())
            })
            .detach();
        });
    Ok(())
}
