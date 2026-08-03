#!/usr/bin/env bash
# Initialize or repair this worker workspace without overwriting user content.
set -euo pipefail

workspace_root="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$workspace_root"

mkdir -p .agents/skills .claude plans projects tmp

link_relative() {
  local target="$1"
  local link_path="$2"
  if [ -L "$link_path" ]; then
    if [ "$(readlink "$link_path")" = "$target" ]; then
      return
    fi
    printf 'Skip: %s is an existing link to %s\n' "$link_path" "$(readlink "$link_path")" >&2
    return
  fi
  if [ -e "$link_path" ]; then
    printf 'Skip: %s already exists and is not a symbolic link\n' "$link_path" >&2
    return
  fi
  ln -s "$target" "$link_path"
}

link_relative "AGENTS.md" "CLAUDE.md"
link_relative "../.agents/skills" ".claude/skills"

if [ ! -d .git ]; then
  git init --quiet
  printf 'Initialized Git repository.\n'
fi

if [ "${1:-}" = "--install-pen-cli" ]; then
  if ! command -v npm >/dev/null 2>&1; then
    printf 'npm is required to install the pen.dev CLI (Node.js 18+).\n' >&2
    exit 1
  fi
  npm install --global @pen.dev/cli
fi

printf 'Worker workspace is ready.\n'
printf 'Pencil MCP: launch and activate the pen.dev desktop app, then open Codex and run /mcp.\n'
