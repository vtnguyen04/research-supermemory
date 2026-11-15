#!/usr/bin/env bash
set -euo pipefail

DEFAULT_REPO_URL="https://github.com/vtnguyen04/research-supermemory.git"
REPO_URL="${SUPERMEMORY_REPO:-${1:-${DEFAULT_REPO_URL}}}"
BIN_DIR="${HOME}/.local/bin"
mkdir -p "${BIN_DIR}"

INSTALL_SPEC="git+${REPO_URL}"
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [ -f "${SCRIPT_DIR}/pyproject.toml" ]; then
    INSTALL_SPEC="${SCRIPT_DIR}"
  fi
fi

echo "==> Installing Research SuperMemory (${INSTALL_SPEC})..."

if command -v uv >/dev/null 2>&1; then
  uv tool install --force "${INSTALL_SPEC}"
elif command -v pipx >/dev/null 2>&1; then
  pipx install --force "${INSTALL_SPEC}"
else
  VENV_DIR="${HOME}/.local/share/supermemory-venv"
  python3 -m venv "${VENV_DIR}"
  "${VENV_DIR}/bin/pip" install --upgrade pip >/dev/null
  "${VENV_DIR}/bin/pip" install --force-reinstall "${INSTALL_SPEC}"
  ln -sf "${VENV_DIR}/bin/supermemory" "${BIN_DIR}/supermemory"
fi

SUPERMEMORY_BIN="${BIN_DIR}/supermemory"
if command -v supermemory >/dev/null 2>&1; then
  SUPERMEMORY_BIN="$(command -v supermemory)"
fi

if command -v agy >/dev/null 2>&1 || [ -x "${BIN_DIR}/agy" ]; then
  echo "==> Validating & installing Antigravity Plugin..."
  "${SUPERMEMORY_BIN}" install-plugin
else
  echo "--> Note: 'agy' binary not found in PATH; skipping Antigravity plugin step."
  echo "    Once Antigravity CLI is installed, run: supermemory install-plugin"
fi

echo ""
echo "✔ SuperMemory installed! Ready to use from anywhere:"
echo "  • Init inside a project:   supermemory init ."
echo "  • Open Project Web Studio: supermemory ui"
echo "  • Open Global Web Studio:  supermemory ui -g"
