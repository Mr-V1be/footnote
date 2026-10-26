#!/usr/bin/env bash
# The local stand in the background: infrastructure containers, the API,
# the worker and the web app. The processes outlive the shell that started
# them; their logs go to .run/logs/, their ids to .run/*.pid.
#   scripts/stand.sh start    containers up, then API, worker and web
#   scripts/stand.sh stop     the processes, then `docker compose stop`
#   scripts/stand.sh status
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="$ROOT/.run"
LOGS="$RUN/logs"
SERVICES=(api worker web)

command_of() {
  case "$1" in
    api) echo "cd '$ROOT' && exec backend/.venv/bin/footnote api" ;;
    worker) echo "cd '$ROOT' && exec backend/.venv/bin/footnote worker" ;;
    web) echo "cd '$ROOT/frontend' && exec pnpm dev" ;;
  esac
}

running() {
  local pid
  pid="$(cat "$RUN/$1.pid" 2>/dev/null || true)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

start() {
  mkdir -p "$LOGS"
  (cd "$ROOT" && docker compose up -d --wait)
  for service in "${SERVICES[@]}"; do
    if running "$service"; then
      echo "$service: already running (pid $(cat "$RUN/$service.pid"))"
      continue
    fi
    # A session of its own: the process group survives the terminal.
    setsid bash -c "$(command_of "$service")" >>"$LOGS/$service.log" 2>&1 < /dev/null &
    echo $! >"$RUN/$service.pid"
    echo "$service: started (pid $!, log .run/logs/$service.log)"
  done
}

stop() {
  for service in "${SERVICES[@]}"; do
    if running "$service"; then
      local pid
      pid="$(cat "$RUN/$service.pid")"
      # The whole group: pnpm's Next.js server is a child of its own.
      kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid"
      echo "$service: stopped"
    fi
    rm -f "$RUN/$service.pid"
  done
  (cd "$ROOT" && docker compose stop)
}

status() {
  for service in "${SERVICES[@]}"; do
    if running "$service"; then
      echo "$service: running (pid $(cat "$RUN/$service.pid"))"
    else
      echo "$service: stopped"
    fi
  done
  (cd "$ROOT" && docker compose ps --format '{{.Service}}: {{.State}}')
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  *) echo "usage: scripts/stand.sh start|stop|status" >&2; exit 2 ;;
esac
