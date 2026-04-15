#!/usr/bin/env bash
# Nightly snapshot of the QuillCV uploads directory on the production host.
#
# Runs on the VM as the deploy user (NOT inside the app container). It reads
# the bind-mounted uploads tree — which Kamal mounts at ~/storage/uploads —
# and writes a dated tarball into ~/storage/backups/, then prunes snapshots
# older than RETENTION_DAYS.
#
# Installation (one-time, from your workstation):
#   scp scripts/backup_uploads.sh deploy@<host>:~/scripts/
#   ssh deploy@<host> '
#       chmod +x ~/scripts/backup_uploads.sh
#       mkdir -p ~/storage/backups
#       ( crontab -l 2>/dev/null | grep -v backup_uploads.sh
#         echo "0 3 * * * ~/scripts/backup_uploads.sh >> ~/storage/backups/backup.log 2>&1"
#       ) | crontab -
#   '
#
# Restore (manual):
#   tar -xzf ~/storage/backups/uploads-YYYY-MM-DD.tar.gz -C ~/storage/
#   # produces ~/storage/uploads/

set -euo pipefail

SRC="${HOME}/storage/uploads"
DEST_DIR="${HOME}/storage/backups"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

log() { printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }

if [[ ! -d "$SRC" ]]; then
    log "ERROR: source directory $SRC does not exist; nothing to back up"
    exit 1
fi

mkdir -p "$DEST_DIR"

TIMESTAMP=$(date -u +'%Y-%m-%d')
FINAL="${DEST_DIR}/uploads-${TIMESTAMP}.tar.gz"
TMP="${FINAL}.tmp"

# Snapshot to a temp file first, then rename so cron never leaves a partial
# tarball where a restore script might pick it up.
log "Creating snapshot → $FINAL"
tar -czf "$TMP" -C "$(dirname "$SRC")" "$(basename "$SRC")"
mv "$TMP" "$FINAL"

SIZE=$(du -h "$FINAL" | awk '{print $1}')
log "Snapshot complete (${SIZE})"

# Prune snapshots older than the retention window.
PRUNED=$(find "$DEST_DIR" -maxdepth 1 -type f -name 'uploads-*.tar.gz' -mtime "+${RETENTION_DAYS}" -print -delete | wc -l)
if (( PRUNED > 0 )); then
    log "Pruned ${PRUNED} snapshot(s) older than ${RETENTION_DAYS} days"
fi

log "Done"
