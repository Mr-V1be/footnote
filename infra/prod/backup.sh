#!/usr/bin/env sh
# Nightly backups: both databases as custom-format dumps and the uploaded
# files as a tarball, kept for SNOSKA_BACKUP_KEEP_DAYS days in /backups.
# Runs in the PostgreSQL image (its pg_dump matches the server).
#   backup.sh          sleep until SNOSKA_BACKUP_HOUR, back up, repeat
#   backup.sh now      one backup at once
set -eu

HOUR="${SNOSKA_BACKUP_HOUR:-2}"
KEEP="${SNOSKA_BACKUP_KEEP_DAYS:-14}"
export PGHOST=postgres PGUSER=postgres PGPASSWORD="${POSTGRES_SUPERUSER_PASSWORD:?}"

backup() {
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  target="/backups/$stamp"
  mkdir -p "$target"
  for db in snoska keycloak; do
    pg_dump --format=custom --no-owner --file="$target/$db.dump" "$db"
  done
  tar -czf "$target/blobs.tar.gz" -C /blobs .
  find /backups -mindepth 1 -maxdepth 1 -type d -mtime "+$KEEP" -exec rm -rf {} +
  echo "backup $stamp: $(du -sh "$target" | cut -f1)"
}

if [ "${1:-}" = "now" ]; then
  backup
  exit 0
fi

while true; do
  now="$(date -u +%s)"
  next="$(date -u -d "$(date -u +%Y-%m-%d) $HOUR:00" +%s)"
  [ "$next" -gt "$now" ] || next=$((next + 86400))
  sleep $((next - now))
  backup || echo "backup failed" >&2
done
