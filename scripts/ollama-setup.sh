#!/usr/bin/env bash
# Local model runtime for Snoska.
#
# Runs `ollama serve` as a user process on the project's port (models live in
# ~/.ollama), pulls the configured models and checks that they answer.
#
#   scripts/ollama-setup.sh            start, pull and verify (default)
#   scripts/ollama-setup.sh start      start the server only
#   scripts/ollama-setup.sh pull       pull the configured models
#   scripts/ollama-setup.sh verify     embed and chat once
#   scripts/ollama-setup.sh status     show server state and local models
#   scripts/ollama-setup.sh stop       stop the server started by this script
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/.run"
PID_FILE="$RUN_DIR/ollama.pid"
LOG_FILE="$RUN_DIR/ollama.log"
RUNTIME_DIR="$RUN_DIR/ollama-runtime"
READY_TIMEOUT_SECONDS=60

env_value() {
  local key="$1" fallback="$2" value=""
  if [[ -f "$ROOT/.env" ]]; then
    value="$(grep -E "^${key}=" "$ROOT/.env" | tail -n1 | cut -d= -f2- || true)"
  fi
  printf '%s' "${value:-$fallback}"
}

PORT="$(env_value SNOSKA_OLLAMA_PORT 46340)"
LLM_MODEL="$(env_value SNOSKA_LLM_MODEL qwen3.5:9b)"
EMBEDDING_MODEL="$(env_value SNOSKA_EMBEDDING_MODEL bge-m3:567m)"
export OLLAMA_HOST="127.0.0.1:${PORT}"
BASE_URL="http://${OLLAMA_HOST}"

log() { printf '[ollama] %s\n' "$*"; }

require_binary() {
  if ! command -v ollama >/dev/null 2>&1; then
    log "the ollama binary is not installed; see https://ollama.com/download"
    exit 1
  fi
}

# Ollama looks for its GPU libraries next to the executable (../lib/ollama)
# and aborts when any entry there is unreadable for the current user (some
# installs ship a root-only directory). In that case the server runs from a
# private copy of the binary whose library directory links only the readable
# entries, so GPU acceleration keeps working without touching the system.
server_binary() {
  local system_binary system_libs entry name
  system_binary="$(readlink -f "$(command -v ollama)")"
  system_libs="$(dirname "$system_binary")/../lib/ollama"
  if [[ ! -d "$system_libs" ]] || [[ -z "$(find "$system_libs" -maxdepth 1 ! -readable -print -quit 2>/dev/null)" ]]; then
    printf '%s' "$system_binary"
    return
  fi
  mkdir -p "$RUNTIME_DIR/bin" "$RUNTIME_DIR/lib/ollama"
  if ! cmp -s "$system_binary" "$RUNTIME_DIR/bin/ollama"; then
    cp "$system_binary" "$RUNTIME_DIR/bin/ollama"
  fi
  find "$RUNTIME_DIR/lib/ollama" -maxdepth 1 -type l -delete
  for entry in "$system_libs"/*; do
    name="$(basename "$entry")"
    if [[ -r "$entry" ]] && { [[ ! -d "$entry" ]] || [[ -x "$entry" ]]; } && [[ -e "$(readlink -f "$entry")" ]] && [[ -r "$(readlink -f "$entry")" ]]; then
      ln -sfn "$(readlink -f "$entry")" "$RUNTIME_DIR/lib/ollama/$name"
    fi
  done
  printf '%s' "$RUNTIME_DIR/bin/ollama"
}

is_up() { curl -fsS --max-time 2 "${BASE_URL}/api/version" >/dev/null 2>&1; }

start() {
  require_binary
  if is_up; then
    log "already running on ${OLLAMA_HOST}"
    return
  fi
  mkdir -p "$RUN_DIR"
  local binary
  binary="$(server_binary)"
  log "starting ${binary#"$ROOT"/} on ${OLLAMA_HOST} (log: ${LOG_FILE#"$ROOT"/})"
  nohup "$binary" serve >"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  for _ in $(seq 1 "$READY_TIMEOUT_SECONDS"); do
    if is_up; then
      log "ready: $(curl -fsS "${BASE_URL}/api/version")"
      grep -m1 -o 'msg="inference compute".*description="[^"]*"' "$LOG_FILE" | sed 's/.*description=/[ollama] compute: /' || true
      return
    fi
    sleep 1
  done
  log "did not become ready in ${READY_TIMEOUT_SECONDS}s; see ${LOG_FILE}"
  exit 1
}

pull() {
  require_binary
  is_up || start
  for model in "$EMBEDDING_MODEL" "$LLM_MODEL"; do
    if ollama show "$model" >/dev/null 2>&1; then
      log "model ${model} is present"
    else
      log "pulling ${model}"
      ollama pull "$model"
    fi
  done
}

verify() {
  is_up || { log "server is not running"; exit 1; }
  local dims
  dims="$(curl -fsS "${BASE_URL}/api/embed" \
    -d "{\"model\":\"${EMBEDDING_MODEL}\",\"input\":[\"Согласие на обработку персональных данных\"]}" \
    | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["embeddings"][0]))')"
  log "embedding model ${EMBEDDING_MODEL}: ${dims} dimensions"
  curl -fsS "${BASE_URL}/api/chat" -d "{
      \"model\": \"${LLM_MODEL}\",
      \"stream\": false,
      \"think\": false,
      \"options\": {\"num_predict\": 40, \"temperature\": 0},
      \"messages\": [{\"role\": \"user\", \"content\": \"Ответь одним словом: столица России?\"}]
    }" | python3 -c 'import json,sys; b=json.load(sys.stdin); print("[ollama] language model '"${LLM_MODEL}"':", b["message"]["content"].strip()[:80])'
}

status() {
  if is_up; then
    log "running on ${OLLAMA_HOST}"
    ollama list
  else
    log "not running"
  fi
}

stop() {
  if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    kill "$(cat "$PID_FILE")"
    rm -f "$PID_FILE"
    log "stopped"
  else
    log "no server started by this script is running"
  fi
}

case "${1:-all}" in
  all) start; pull; verify ;;
  start) start ;;
  pull) pull ;;
  verify) verify ;;
  status) status ;;
  stop) stop ;;
  *) echo "usage: $0 [all|start|pull|verify|status|stop]" >&2; exit 2 ;;
esac
