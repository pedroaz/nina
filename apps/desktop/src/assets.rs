use std::{borrow::Cow, sync::Arc};

use gpui::{AssetSource, Result, SharedString};

const NINA_SVG: &[u8] = include_bytes!("../assets/icons/nina.svg");
const NINA_PNG_256: &[u8] = include_bytes!("../assets/icons/png/256.png");
const NINA_ICON_PATH: &str = "icons/nina.svg";

pub struct DesktopAssets;

impl AssetSource for DesktopAssets {
    fn load(&self, path: &str) -> Result<Option<Cow<'static, [u8]>>> {
        if path == NINA_ICON_PATH {
            return Ok(Some(Cow::Borrowed(NINA_SVG)));
        }

        gpui_component_assets::Assets.load(path)
    }

    fn list(&self, path: &str) -> Result<Vec<SharedString>> {
        let mut assets = gpui_component_assets::Assets.list(path)?;
        if NINA_ICON_PATH.starts_with(path)
            && !assets.iter().any(|asset| asset.as_ref() == NINA_ICON_PATH)
        {
            assets.push(NINA_ICON_PATH.into());
        }
        Ok(assets)
    }
}

pub fn window_icon() -> Option<Arc<image::RgbaImage>> {
    image::load_from_memory(NINA_PNG_256)
        .ok()
        .map(|image| Arc::new(image.to_rgba8()))
}
