#!/usr/bin/env bash
# Symlinks vendored Claude Code plugins into ~/.claude/plugins/ at session start.
# Idempotent: skips if a plugin entry already exists at the target path.
# Safe-fails: never blocks session start on filesystem errors.

set -u

project_dir="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
vendor_dir="$project_dir/tools/agents"
plugins_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins"

mkdir -p "$plugins_dir" 2>/dev/null || exit 0

for plugin in superpowers caveman; do
  src="$vendor_dir/$plugin"
  dst="$plugins_dir/$plugin"
  [[ -e "$dst" || -L "$dst" ]] && continue
  [[ -d "$src" ]] || continue
  ln -sfn "$src" "$dst" 2>/dev/null || true
done

exit 0
