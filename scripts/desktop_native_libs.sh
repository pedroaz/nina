#!/usr/bin/env sh
set -eu

target_dir="${1:?usage: desktop_native_libs.sh TARGET_DIR}"
missing=0

mkdir -p "$target_dir"

if [ "$(uname -s)" != "Linux" ]; then
  exit 0
fi

find_runtime_lib() {
  lib_name="$1"
  if command -v ldconfig >/dev/null 2>&1; then
    ldconfig -p 2>/dev/null | awk -v lib="$lib_name" '$1 == lib { print $NF; exit }'
  fi

  for lib_dir in /lib/x86_64-linux-gnu /usr/lib/x86_64-linux-gnu /lib64 /usr/lib64 /usr/lib; do
    if [ -e "$lib_dir/$lib_name" ]; then
      printf '%s\n' "$lib_dir/$lib_name"
      return 0
    fi
  done
}

link_runtime_lib() {
  link_name="$1"
  runtime_name="$2"
  runtime_path="$(find_runtime_lib "$runtime_name" | head -n 1 || true)"

  if [ -z "$runtime_path" ]; then
    printf 'Missing native runtime library: %s\n' "$runtime_name" >&2
    missing=1
    return 0
  fi

  ln -sf "$runtime_path" "$target_dir/$link_name"
}

link_runtime_lib libxcb.so libxcb.so.1
link_runtime_lib libxkbcommon.so libxkbcommon.so.0
link_runtime_lib libxkbcommon-x11.so libxkbcommon-x11.so.0

if [ "$missing" -ne 0 ]; then
  cat >&2 <<'EOF'
GPUI needs xcb, xkbcommon, and xkbcommon-x11 to link on Linux.

Install the development packages if the runtime libraries are not present:
  sudo apt install libxcb1-dev libxkbcommon-dev libxkbcommon-x11-dev
EOF
  exit 1
fi
