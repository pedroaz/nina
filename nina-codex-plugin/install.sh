#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_SRC="$SCRIPT_DIR/files/nina-codex"

PLUGIN_PARENT="${NINA_CODEX_PLUGIN_PARENT:-$HOME/plugins}"
AGENTS_HOME="${AGENTS_HOME:-$HOME/.agents}"
PLUGIN_DST="$PLUGIN_PARENT/nina-codex"
MARKETPLACE_DST="$AGENTS_HOME/plugins/marketplace.json"

if [ ! -d "$PLUGIN_SRC" ]; then
  echo "Missing plugin source: $PLUGIN_SRC" >&2
  exit 1
fi

mkdir -p "$PLUGIN_PARENT" "$AGENTS_HOME/plugins"
rm -rf "$PLUGIN_DST"
cp -R "$PLUGIN_SRC" "$PLUGIN_DST"
chmod +x "$PLUGIN_DST/hooks/nina_hook.py"

PLUGIN_DST="$PLUGIN_DST" MARKETPLACE_DST="$MARKETPLACE_DST" node <<'NODE'
const fs = require('fs');
const path = require('path');

const pluginDir = process.env.PLUGIN_DST;
const marketplacePath = process.env.MARKETPLACE_DST;
const hookPath = path.join(pluginDir, 'hooks', 'nina_hook.py');
const hooksJsonPath = path.join(pluginDir, 'hooks', 'hooks.json');

let hooksJson = fs.readFileSync(hooksJsonPath, 'utf8');
hooksJson = hooksJson.replaceAll('__NINA_CODEX_HOOK__', hookPath);
fs.writeFileSync(hooksJsonPath, hooksJson);

const entry = {
  name: 'nina-codex',
  source: {
    source: 'local',
    path: './plugins/nina-codex'
  },
  policy: {
    installation: 'AVAILABLE',
    authentication: 'ON_INSTALL'
  },
  category: 'Productivity'
};

let marketplace;
if (fs.existsSync(marketplacePath)) {
  marketplace = JSON.parse(fs.readFileSync(marketplacePath, 'utf8'));
  if (!marketplace || typeof marketplace !== 'object' || Array.isArray(marketplace)) {
    throw new Error('marketplace.json must contain a JSON object');
  }
  marketplace.name ??= 'personal';
  marketplace.interface ??= { displayName: 'Personal' };
  marketplace.plugins ??= [];
  if (!Array.isArray(marketplace.plugins)) {
    throw new Error('marketplace.json plugins field must be an array');
  }
} else {
  marketplace = {
    name: 'personal',
    interface: { displayName: 'Personal' },
    plugins: []
  };
}

const index = marketplace.plugins.findIndex((plugin) => plugin && plugin.name === entry.name);
if (index >= 0) {
  marketplace.plugins[index] = entry;
} else {
  marketplace.plugins.push(entry);
}

fs.mkdirSync(path.dirname(marketplacePath), { recursive: true });
fs.writeFileSync(marketplacePath, JSON.stringify(marketplace, null, 2) + '\n');
NODE

echo "Installed nina-codex plugin source to: $PLUGIN_DST"
echo "Updated personal marketplace: $MARKETPLACE_DST"
echo "Install or refresh it with: codex plugin add nina-codex@personal"
echo "Start a new Codex thread after installing so the plugin is loaded."
