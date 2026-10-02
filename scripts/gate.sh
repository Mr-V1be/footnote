#!/usr/bin/env bash
# Quality gate: the same checks run locally and in CI.
#
#   scripts/gate.sh            everything
#   scripts/gate.sh backend    source limits + backend checks
#   scripts/gate.sh frontend   source limits + frontend checks
#
# Backend integration tests need PostgreSQL with the `snoska_test` database
# (the compose stack locally, a service container in CI).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCOPE="${1:-all}"

step() { printf '\n\033[1m▶ %s\033[0m\n' "$*"; }

step "source limits (≤700 lines per file, ≤15 source files per folder)"
python3 "$ROOT/scripts/check_source_limits.py"

if [[ "$SCOPE" == all || "$SCOPE" == backend ]]; then
  cd "$ROOT/backend"
  step "backend: ruff lint"
  uv run --frozen ruff check src tests migrations
  uv run --frozen ruff check --config pyproject.toml ../scripts
  step "backend: ruff format"
  uv run --frozen ruff format --check src tests migrations
  uv run --frozen ruff format --config pyproject.toml --check ../scripts
  step "backend: mypy --strict"
  uv run --frozen mypy
  step "backend: import contracts"
  uv run --frozen lint-imports
  step "backend: tests"
  uv run --frozen pytest
fi

if [[ "$SCOPE" == all || "$SCOPE" == frontend ]]; then
  cd "$ROOT/frontend"
  step "frontend: generated API types are up to date"
  pnpm run --silent api:check
  step "frontend: typecheck"
  pnpm run --silent typecheck
  step "frontend: eslint"
  pnpm run --silent lint
  step "frontend: stylelint"
  pnpm run --silent lint:styles
  step "frontend: prettier"
  pnpm run --silent format:check
fi

printf '\n\033[1;32m✔ gate passed (%s)\033[0m\n' "$SCOPE"
