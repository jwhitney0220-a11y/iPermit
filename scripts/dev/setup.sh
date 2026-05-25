#!/usr/bin/env bash
#
# Local developer bootstrap for the iPermit monorepo (T01-12).
#
# Idempotent and safe-fail: re-running it does no harm, and a missing optional
# tool prints a hint rather than aborting the whole script. It sets up the
# Python tooling virtualenv, installs Ruff + pre-commit, registers the git
# hooks, and points you at the frontend install step.
#
# Usage:  ./scripts/dev/setup.sh
set -euo pipefail

# Resolve the repo root from this script's location so it works from anywhere.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

VENV_DIR="${REPO_ROOT}/.venv"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$1"; }

# --- Python tooling virtualenv ------------------------------------------------
setup_python_venv() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found — install Python 3.11+ (see ADR-0001) and re-run."
    return 0
  fi
  if [ ! -d "${VENV_DIR}" ]; then
    log "Creating tooling virtualenv at .venv"
    python3 -m venv "${VENV_DIR}"
  else
    log "Reusing existing .venv"
  fi
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
  python -m pip install --quiet --upgrade pip
  log "Installing Ruff and pre-commit into .venv"
  python -m pip install --quiet "ruff==0.15.8" "pre-commit>=3.5"
}

# --- Git hooks ----------------------------------------------------------------
install_git_hooks() {
  if command -v pre-commit >/dev/null 2>&1; then
    log "Installing pre-commit git hooks"
    pre-commit install
  else
    warn "pre-commit not on PATH after install — open a new shell and re-run."
  fi
}

# --- Frontend hint ------------------------------------------------------------
frontend_hint() {
  if [ -f "${REPO_ROOT}/.nvmrc" ]; then
    log "Node version pinned in .nvmrc: $(cat "${REPO_ROOT}/.nvmrc")"
  fi
  warn "Frontend deps are per-app. In each app (apps/web, apps/analyst-portal):"
  printf '      nvm use && npm install\n'
}

main() {
  log "Bootstrapping iPermit developer environment in ${REPO_ROOT}"
  setup_python_venv
  install_git_hooks
  frontend_hint
  log "Done. Activate the tooling venv with:  source .venv/bin/activate"
}

main "$@"
