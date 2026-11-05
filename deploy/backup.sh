#!/bin/sh
# Back up the SQLite database and the app's files, on a server without
# Docker (with Docker, use deploy/docker/backup.sh). Run from the app's
# folder, by hand or from cron:
#
#   15 1 * * *  cd /home/tgk/projects/welfare-3 && sh deploy/backup.sh >> backups/backup.log 2>&1
#
# Writes backups/welfare-<date>.db.gz and backups/files-<date>.tar.gz and
# keeps the last KEEP_DAYS days (default 14). Copy them off the server too:
# a backup on the same disk doesn't survive losing the server.
set -eu

KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y-%m-%d_%H%M)"
mkdir -p backups

DB="$(sed -n 's|^DATABASE_URL=sqlite:///||p' .env)"
if [ -z "$DB" ] || [ ! -f "$DB" ]; then
    echo "No SQLite database found from DATABASE_URL in .env" >&2
    exit 1
fi

# SQLite's own backup copies a consistent database while the app runs
venv/bin/python - "$DB" "backups/welfare-$STAMP.db" <<'EOF'
import sqlite3, sys
source, target = sqlite3.connect(sys.argv[1]), sqlite3.connect(sys.argv[2])
with target:
    source.backup(target)
target.close(); source.close()
EOF
gzip "backups/welfare-$STAMP.db"

# Uploaded logos and stored report files (logs are left out)
tar -czf "backups/files-$STAMP.tar.gz" --ignore-failed-read uploads reports instance/branding 2>/dev/null || true

find backups -name 'welfare-*.db.gz' -mtime +"$KEEP_DAYS" -delete
find backups -name 'files-*.tar.gz' -mtime +"$KEEP_DAYS" -delete

echo "$(date '+%F %T') backed up: welfare-$STAMP.db.gz files-$STAMP.tar.gz"

# Restore:
#   sudo systemctl stop welfare3
#   gunzip -c backups/welfare-<date>.db.gz > <the DATABASE_URL file>
#   tar -xzf backups/files-<date>.tar.gz
#   sudo systemctl start welfare3
