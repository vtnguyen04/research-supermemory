#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
mkdir -p "${BIN_DIR}"

echo "==> Installing SuperMemory Harness CLI & SDK..."

if command -v uv >/dev/null 2>&1; then
  uv tool install --force "${REPO_DIR}"
elif command -v pipx >/dev/null 2>&1; then
  pipx install --force "${REPO_DIR}"
else
  VENV_DIR="${HOME}/.local/share/supermemory-venv"
  python3 -m venv "${VENV_DIR}"
  "${VENV_DIR}/bin/pip" install --upgrade pip >/dev/null
  "${VENV_DIR}/bin/pip" install --force-reinstall "${REPO_DIR}"
  ln -sf "${VENV_DIR}/bin/supermemory" "${BIN_DIR}/supermemory"
fi

SUPERMEMORY_BIN="${BIN_DIR}/supermemory"
if command -v supermemory >/dev/null 2>&1; then
  SUPERMEMORY_BIN="$(command -v supermemory)"
fi

if command -v agy >/dev/null 2>&1 || [ -x "${BIN_DIR}/agy" ]; then
  echo "==> Installing SuperMemory Plugin into Antigravity CLI..."
  "${SUPERMEMORY_BIN}" install-plugin
else
  echo "--> Note: 'agy' binary not found in PATH; skipping Antigravity plugin step."
  echo "    Once Antigravity CLI is installed, run: supermemory install-plugin"
fi

echo ""
echo "✔ SuperMemory installed! Quick start:"
echo "  1. Ensure ~/.local/bin is in PATH: export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "  2. Initialize inside any project:  supermemory init ."
echo "  3. Launch Web Studio (Local/Global): supermemory ui   (or: supermemory ui -g)"
