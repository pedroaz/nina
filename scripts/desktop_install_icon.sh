#!/usr/bin/env sh
set -eu

if [ "$(uname -s)" != "Linux" ]; then
    echo "Desktop icon install is only needed on Linux; skipping."
    exit 0
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
icon_dir="$repo_dir/apps/desktop/assets/icons"
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
apps_dir="$data_home/applications"
icons_root="$data_home/icons/hicolor"
desktop_file="$apps_dir/nina.desktop"
desktop_fallback_file="$apps_dir/nina-desktop.desktop"

if [ ! -f "$icon_dir/nina.svg" ]; then
    echo "Missing desktop icon source: $icon_dir/nina.svg" >&2
    exit 1
fi

for size in 16 24 32 48 64 128 256 512 1024; do
    src="$icon_dir/png/$size.png"
    if [ ! -f "$src" ]; then
        echo "Missing desktop icon export: $src" >&2
        exit 1
    fi
done

desktop_exec_arg=$(printf '%s' "$repo_dir" | sed 's/\\/\\\\/g; s/"/\\"/g; s/`/\\`/g; s/\$/\\$/g')
desktop_tmp=$(mktemp)
desktop_fallback_tmp=$(mktemp)
trap 'rm -f "$desktop_tmp" "$desktop_fallback_tmp"' EXIT HUP INT TERM

for size in 16 24 32 48 64 128 256 512 1024; do
    install -Dm644 "$icon_dir/png/$size.png" "$icons_root/${size}x${size}/apps/nina.png"
done
install -Dm644 "$icon_dir/nina.svg" "$icons_root/scalable/apps/nina.svg"

cat > "$desktop_tmp" <<EOF
[Desktop Entry]
Type=Application
Name=Nina
Comment=Local operations desktop
Exec=make -C "$desktop_exec_arg" desktop
Icon=nina
Terminal=false
Categories=Utility;
StartupNotify=true
StartupWMClass=nina
Keywords=Nina;operations;tasks;automation;
EOF

cat > "$desktop_fallback_tmp" <<EOF
[Desktop Entry]
Type=Application
Name=Nina Desktop
Comment=Local operations desktop
Exec=make -C "$desktop_exec_arg" desktop
Icon=nina
Terminal=false
Categories=Utility;
StartupNotify=true
StartupWMClass=nina-desktop
NoDisplay=true
Keywords=Nina;operations;tasks;automation;
EOF

install -Dm644 "$desktop_tmp" "$desktop_file"
install -Dm644 "$desktop_fallback_tmp" "$desktop_fallback_file"

if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$desktop_file" "$desktop_fallback_file"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$apps_dir" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t "$icons_root" >/dev/null 2>&1 || true
fi

if command -v xdg-icon-resource >/dev/null 2>&1; then
    xdg-icon-resource forceupdate --theme hicolor >/dev/null 2>&1 || true
fi

if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
    kbuildsycoca5 --noincremental >/dev/null 2>&1 || true
fi

touch "$icons_root"

echo "Installed Nina desktop metadata:"
echo "  $desktop_file"
echo "  $desktop_fallback_file"
echo "  $icons_root/*/apps/nina.png"
echo "  $icons_root/scalable/apps/nina.svg"
