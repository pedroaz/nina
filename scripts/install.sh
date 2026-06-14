#!/usr/bin/env sh
set -eu

REPOSITORY="${NINA_REPOSITORY:-__NINA_REPOSITORY__}"
CHANNEL="${NINA_CHANNEL:-latest}"
INSTALL_ROOT="${NINA_INSTALL_ROOT:-$HOME/.nina}"
APP_DIR="$INSTALL_ROOT/app"
BIN_DIR="$INSTALL_ROOT/bin"
LAUNCHER_DIR="${NINA_LAUNCHER_DIR:-$HOME/.local/bin}"
DRY_RUN=0

download() {
  url="$1"
  dest="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$dest"
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$url" -O "$dest"
  else
    echo "curl or wget is required." >&2
    exit 1
  fi
}

detect_target() {
  os="$(uname -s)"
  arch="$(uname -m)"
  case "$os" in
    Linux) platform="linux" ;;
    Darwin) platform="macos" ;;
    *) echo "Unsupported OS: $os" >&2; exit 1 ;;
  esac
  case "$arch" in
    x86_64|amd64) machine="x64" ;;
    arm64|aarch64) machine="arm64" ;;
    *) echo "Unsupported architecture: $arch" >&2; exit 1 ;;
  esac
  if [ "$platform" = "linux" ] && [ "$machine" != "x64" ]; then
    echo "Unsupported Linux architecture: $arch" >&2
    exit 1
  fi
  printf '%s-%s\n' "$platform" "$machine"
}

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return
  fi
  echo "Installing uv..."
  uv_install="$tmp_dir/uv-install.sh"
  download https://astral.sh/uv/install.sh "$uv_install"
  sh "$uv_install"
  export PATH="$HOME/.local/bin:$PATH"
}

target="$(detect_target)"
asset="nina-latest-${target}.tar.gz"
url="https://github.com/${REPOSITORY}/releases/download/${CHANNEL}/${asset}"
tmp_dir="$(mktemp -d)"

cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

echo "Installing Nina ${CHANNEL} for ${target} from ${REPOSITORY}"
echo "Archive: ${url}"

if [ "$DRY_RUN" = "1" ]; then
  echo "Install root: $INSTALL_ROOT"
  echo "Launcher: $LAUNCHER_DIR/nina"
  exit 0
fi

ensure_uv
mkdir -p "$APP_DIR" "$BIN_DIR" "$LAUNCHER_DIR"
download "$url" "$tmp_dir/$asset"
tar -xzf "$tmp_dir/$asset" -C "$tmp_dir"
uv venv "$APP_DIR"
"$APP_DIR/bin/python" -m pip install --upgrade pip
"$APP_DIR/bin/python" -m pip install "$tmp_dir"/wheels/*.whl
cp "$tmp_dir/bin/nina-tui" "$BIN_DIR/nina-tui"
chmod +x "$BIN_DIR/nina-tui"
cat > "$LAUNCHER_DIR/nina" <<EOF
#!/usr/bin/env sh
export NINA_TUI_BIN="$BIN_DIR/nina-tui"
exec "$APP_DIR/bin/nina" "\$@"
EOF
chmod +x "$LAUNCHER_DIR/nina"

echo "Nina installed."
echo "Make sure $LAUNCHER_DIR is on PATH."
echo "Try: nina version"
