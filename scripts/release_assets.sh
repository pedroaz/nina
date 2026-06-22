#!/usr/bin/env sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
release_dir="${NINA_PACKAGE_DIR:-$repo_dir/release}"
assets_dir="$release_dir/assets"
staging_dir="$release_dir/staging"
wheels_dir="$release_dir/wheels"
package_name="${NINA_PACKAGE_NAME:-local}"
components="${NINA_PACKAGE_COMPONENTS:-all}"

log() {
    printf '%s\n' "$*"
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Required command not found on PATH: %s\n' "$1" >&2
        exit 1
    fi
}

reset_release_dir() {
    rm -rf "$release_dir"
    mkdir -p "$assets_dir" "$staging_dir"
}

build_python_wheels() {
    require_command uv
    log "Building Python wheels..."
    mkdir -p "$wheels_dir"
    (cd "$repo_dir/packages/nina_core" && uv build --wheel --out-dir "$wheels_dir")
    (cd "$repo_dir/apps/server" && uv build --wheel --out-dir "$wheels_dir")
    (cd "$repo_dir/apps/cli" && uv build --wheel --out-dir "$wheels_dir")
}

package_cli_tarball() {
    target="$1"
    staging="$staging_dir/nina-$target"
    mkdir -p "$staging/wheels"
    cp "$wheels_dir"/*.whl "$staging/wheels/"
    tar -C "$staging" -czf "$assets_dir/nina-$package_name-$target.tar.gz" .
}

package_cli_zip() {
    target="$1"
    staging="$staging_dir/nina-$target"
    mkdir -p "$staging/wheels"
    cp "$wheels_dir"/*.whl "$staging/wheels/"
    (cd "$staging" && zip -qr "$assets_dir/nina-$package_name-$target.zip" .)
}

package_cli_assets() {
    require_command tar
    require_command zip
    build_python_wheels

    log "Packaging CLI assets..."
    package_cli_tarball linux-x64
    package_cli_tarball macos-x64
    package_cli_tarball macos-arm64
    package_cli_zip windows-x64
}

detect_desktop_target() {
    os_name=$(uname -s)
    arch_name=$(uname -m)

    case "$os_name" in
        Linux) platform=linux ;;
        Darwin) platform=macos ;;
        MINGW*|MSYS*|CYGWIN*) platform=windows ;;
        *) printf 'Unsupported desktop release OS: %s\n' "$os_name" >&2; exit 1 ;;
    esac

    case "$arch_name" in
        x86_64|amd64) machine=x64 ;;
        arm64|aarch64) machine=arm64 ;;
        *) printf 'Unsupported desktop release architecture: %s\n' "$arch_name" >&2; exit 1 ;;
    esac

    if [ "$platform" = "linux" ] && [ "$machine" != "x64" ]; then
        printf 'Unsupported Linux desktop release architecture: %s\n' "$arch_name" >&2
        exit 1
    fi

    if [ "$platform" = "windows" ] && [ "$machine" != "x64" ]; then
        printf 'Unsupported Windows desktop release architecture: %s\n' "$arch_name" >&2
        exit 1
    fi

    printf '%s-%s\n' "$platform" "$machine"
}

desktop_binary_name() {
    case "$1" in
        windows-*) printf 'nina-desktop.exe\n' ;;
        *) printf 'nina-desktop\n' ;;
    esac
}

write_desktop_package_readme() {
    cat > "$1" <<EOF
Nina Desktop
============

This archive contains the Nina desktop client for $2.

Start the Nina daemon before launching the desktop app:

  nina daemon start

Then run:

  bin/$(desktop_binary_name "$2")

The desktop client talks only to the local Nina daemon.
EOF
}

write_linux_desktop_file() {
    applications_dir="$1"
    mkdir -p "$applications_dir"
    cat > "$applications_dir/nina.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Nina
Comment=Local operations desktop
Exec=nina-desktop
Icon=nina
Terminal=false
Categories=Utility;
StartupNotify=true
StartupWMClass=nina
Keywords=Nina;operations;tasks;automation;
EOF
}

copy_desktop_icons() {
    staging="$1"
    icon_dir="$repo_dir/apps/desktop/assets/icons"

    mkdir -p "$staging/share/nina/icons/png" "$staging/share/icons/hicolor/scalable/apps"
    cp "$icon_dir/nina.svg" "$staging/share/nina/icons/nina.svg"
    cp "$icon_dir/nina.ico" "$staging/share/nina/icons/nina.ico"
    cp "$icon_dir/png/"*.png "$staging/share/nina/icons/png/"
    cp "$icon_dir/nina.svg" "$staging/share/icons/hicolor/scalable/apps/nina.svg"

    for size in 16 24 32 48 64 128 256 512 1024; do
        mkdir -p "$staging/share/icons/hicolor/${size}x${size}/apps"
        cp "$icon_dir/png/$size.png" "$staging/share/icons/hicolor/${size}x${size}/apps/nina.png"
    done
}

build_desktop_binary() {
    require_command cargo
    target="$1"
    detected_target=$(detect_desktop_target)
    if [ "$target" != "$detected_target" ]; then
        printf 'Desktop release target %s must be built on matching host %s.\n' "$target" "$detected_target" >&2
        exit 1
    fi

    native_lib_dir="$repo_dir/apps/desktop/.native-libs"
    sh "$repo_dir/scripts/desktop_native_libs.sh" "$native_lib_dir"

    rustflags="-L native=$native_lib_dir"
    if [ -n "${RUSTFLAGS:-}" ]; then
        rustflags="$rustflags $RUSTFLAGS"
    fi

    log "Building desktop release binary for $target..."
    (
        cd "$repo_dir/apps/desktop"
        RUST_FONTCONFIG_DLOPEN=1 RUSTFLAGS="$rustflags" cargo build --release --locked
    )
}

package_desktop_assets() {
    require_command tar
    target="${NINA_DESKTOP_TARGET:-$(detect_desktop_target)}"
    build_desktop_binary "$target"

    binary_name=$(desktop_binary_name "$target")
    binary_path="$repo_dir/apps/desktop/target/release/$binary_name"
    staging="$staging_dir/nina-desktop-$target"

    if [ ! -f "$binary_path" ]; then
        printf 'Desktop binary was not built: %s\n' "$binary_path" >&2
        exit 1
    fi

    log "Packaging desktop asset for $target..."
    mkdir -p "$staging/bin"
    cp "$binary_path" "$staging/bin/$binary_name"
    chmod +x "$staging/bin/$binary_name" 2>/dev/null || true
    copy_desktop_icons "$staging"
    write_desktop_package_readme "$staging/README.txt" "$target"

    if [ "$target" = "linux-x64" ]; then
        write_linux_desktop_file "$staging/share/applications"
    fi

    case "$target" in
        windows-*)
            require_command zip
            (cd "$staging" && zip -qr "$assets_dir/nina-desktop-$package_name-$target.zip" .)
            ;;
        *)
            tar -C "$staging" -czf "$assets_dir/nina-desktop-$package_name-$target.tar.gz" .
            ;;
    esac
}

reset_release_dir

case "$components" in
    all)
        package_cli_assets
        package_desktop_assets
        ;;
    cli)
        package_cli_assets
        ;;
    desktop)
        package_desktop_assets
        ;;
    *)
        printf 'Unsupported PACKAGE_COMPONENTS value: %s\n' "$components" >&2
        printf 'Use all, cli, or desktop.\n' >&2
        exit 1
        ;;
esac

log "Package assets written to $assets_dir"
