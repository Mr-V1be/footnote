#!/usr/bin/env bash
# Load test of the API with k6 in its Docker image (nothing is installed on
# the host). Needs the stand running (make up, make api, make worker) with
# FOOTNOTE_DEMO_MODE=true: the test signs in through the demo client.
#   scripts/load-test.sh               60 seconds
#   DURATION=30s scripts/load-test.sh
#   LIST_RATE=150 REPORT_RATE=50 UPLOAD_RATE=2 CHECK_RATE=2 scripts/load-test.sh   a peak
# The summary goes to .run/k6/summary.json. The demo stand returns to its
# seed afterwards (KEEP_STAND=1 leaves the uploaded copies in place).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K6_IMAGE="grafana/k6:1.3.0"

secret="$(grep -E '^FOOTNOTE_DEMO_CLIENT_SECRET=' "$ROOT/.env" | cut -d= -f2-)"
[[ -n "$secret" ]] || { echo "FOOTNOTE_DEMO_CLIENT_SECRET is not set in .env" >&2; exit 1; }
# The demo password of the seeded owner (public demo data).
password="$(awk '/email: kovaleva@/{found=1} found && /password:/{print $2; exit}' "$ROOT/backend/demo/seed.yaml")"

restore() {
  if [[ "${KEEP_STAND:-0}" != 1 ]]; then
    (cd "$ROOT/backend" && uv run --frozen footnote demo reset && uv run --frozen footnote checks wait)
  fi
}
# Also when k6 fails a threshold.
trap restore EXIT

mkdir -p "$ROOT/.run/k6"
# Secrets reach the container from the environment, not the command line.
DEMO_CLIENT_SECRET="$secret" OWNER_PASSWORD="$password" \
  docker run --rm --network host --user "$(id -u):$(id -g)" \
  -v "$ROOT:/repo:ro" -v "$ROOT/.run/k6:/out" \
  -e DEMO_CLIENT_SECRET -e OWNER_PASSWORD -e DURATION="${DURATION:-60s}" \
  -e LIST_RATE -e REPORT_RATE -e UPLOAD_RATE -e CHECK_RATE \
  "$K6_IMAGE" run --summary-export /out/summary.json /repo/load/k6/snoska.js
