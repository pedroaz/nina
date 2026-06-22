# Nina Desktop

Nina Desktop is a GPUI client for the local Nina daemon. It provides mouse-first controls for daemon-backed workflows while preserving Nina's daemon boundary: the desktop app reads and writes only through localhost HTTP API calls.

## Run

Start the daemon first:

```bash
make dev-start
```

Run the desktop client:

```bash
make desktop
```

The client discovers the active profile from `NINA_CONFIG_DIR` or `NINA_PROFILE`, reads the daemon runtime address and bearer token from the profile directory, and falls back to `http://127.0.0.1:8765`.

The Integrations page lists daemon-reported Confluence, Jira, Slack, and Teams health and lets you save, clear, and test credentials through the daemon API. Stored secrets remain in the active Nina profile under `integrations/*.json`; the desktop only receives field metadata and set/empty status.

The Make targets set `RUST_FONTCONFIG_DLOPEN=1` so Linux builds can use runtime fontconfig loading instead of requiring `fontconfig.pc` through `pkg-config`.

On Linux, GPUI also links against native X11/XKB libraries for run and test binaries. `make desktop` prepares local links to the installed runtime libraries under `.native-libs`. If those runtime libraries are missing, install your distribution's packages for `xcb`, `xkbcommon`, and `xkbcommon-x11`.

`make desktop` also refreshes the Linux desktop metadata under `$XDG_DATA_HOME` (usually `~/.local/share`) so the taskbar can resolve the `nina` app id to the Nina icon.

## Development

```bash
make desktop-fmt
make desktop-clippy
make desktop-test
make desktop-check
```

For a watch loop, install `bacon` and run:

```bash
make desktop-bacon
```

GPUI and GPUI Component are pinned to git revisions in `Cargo.toml` because GPUI Component tracks GPUI APIs that may be newer than crates.io releases.

## Icons

`assets/icons/nina.svg` is the canonical source icon. The PNG exports under `assets/icons/png/` and `assets/icons/nina.ico` are generated from that source for desktop/window packaging. The app embeds `icons/nina.svg` for the sidebar brand mark and uses `assets/icons/png/256.png` for the Linux/X11 window icon.

On Linux, `scripts/desktop_install_icon.sh` installs the PNG/SVG exports into the user hicolor icon theme and writes `nina.desktop` plus a hidden `nina-desktop.desktop` fallback. The primary desktop file matches the GPUI `app_id` so Wayland/KDE panels can show the app icon while the app is launched from `cargo run`.
