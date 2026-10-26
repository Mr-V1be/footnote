#!/usr/bin/env bash
# Refreshes everything on the demo stand that depends on the language and
# embedding models, in this order:
#
#   1. corpus index      152-FZ embedded again            -> pgvector (corpus_embeddings)
#   2. stand reset       seeded organizations from seed   -> demo organizations, files
#   3. recheck           every latest version checked     -> check runs, findings
#   4. benchmark         reference set, the model timed   -> backend/data/quality/benchmark.json,
#                                                            docs/quality.md
#   5. screenshots       milestone 4, 3 sizes x 2 themes  -> docs/screenshots/m4
#   6. landing media     clips and stills of the landing, -> frontend/public/landing/<locale>
#                        in every interface language
#   7. product video     1920x1080 and 1080x1920          -> docs/case/video
#
# The runs leave no trace: the stand is returned to its seed at the end.
#
# Needs the infrastructure, the API, the worker and the web app running
# (make up, make api, make worker, make web) and SNOSKA_DEMO_MODE=true.
#
# Model answers are cached by request, so steps 2, 3, 5-7 cost no requests
# for documents checked before. The benchmark asks the model anew to time
# it: on a free tier it refuses to start when today's requests are not
# enough, and the refresh goes on with the other steps (SKIP_BENCHMARK=1
# leaves it out on purpose).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_URL="${API_URL:-http://127.0.0.1:46301}"
WEB_URL="${WEB_URL:-http://localhost:46300}"

# Each recorder restores the stand to its seed when it ends; here the stand
# is restored once, after the last of them.
export KEEP_STAND=1

step() { printf '\n\033[1m▶ %s\033[0m\n' "$*"; }
footnote() { (cd "$ROOT/backend" && uv run --frozen footnote "$@"); }

step "the stand is up"
curl -fsS "$API_URL/api/health/live" >/dev/null || { echo "the API does not answer at $API_URL" >&2; exit 1; }
curl -fsS -o /dev/null "$WEB_URL/" || { echo "the web app does not answer at $WEB_URL" >&2; exit 1; }

step "1/7 corpus index"
footnote corpus reindex

step "2/7 demo stand reset"
footnote demo reset
footnote checks wait

step "3/7 recheck"
footnote checks recheck
footnote checks wait

step "4/7 benchmark"
if [[ "${SKIP_BENCHMARK:-0}" == 1 ]]; then
  echo "left out (SKIP_BENCHMARK=1): the last measurement stays"
elif ! footnote checks benchmark --markdown ../docs/quality.md; then
  echo "not measured today: the last measurement stays (see the message above)" >&2
fi

cd "$ROOT/frontend"
step "5/7 screenshots"
MILESTONE=m4 node e2e/screenshots.mjs

step "6/7 landing media"
for locale in ru en; do
  LOCALE="$locale" node e2e/landing/record.mjs
done

step "7/7 product video"
node e2e/video/record.mjs

step "the demo stand back to its seed"
footnote demo reset
footnote checks wait

step "done"
echo "review the changes with git status before committing"
