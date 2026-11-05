#!/bin/sh
# Back up the database and the app's files. Run from the app's folder (the
# one with docker-compose.yml), by hand or from cron:
#
#   15 1 * * *  cd /opt/welfare && sh deploy/docker/backup.sh >> backups/backup.log 2>&1
#
# Writes backups/welfare-<date>.sql.gz and backups/files-<date>.tar.gz and
# keeps the last KEEP_DAYS days (default 14). Copy them off the server too:
# a backup on the same disk doesn't survive losing the server.
set -eu

KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y-%m-%d_%H%M)"
mkdir -p backups

docker compose exec -T db pg_dump -U welfare --clean --if-exists welfare \
    | gzip > "backups/welfare-$STAMP.sql.gz.part"
mv "backups/welfare-$STAMP.sql.gz.part" "backups/welfare-$STAMP.sql.gz"

# Uploaded logos and stored report files (logs are left out)
docker compose exec -T web tar -C /app -czf - uploads reports instance/branding \
    > "backups/files-$STAMP.tar.gz.part"
mv "backups/files-$STAMP.tar.gz.part" "backups/files-$STAMP.tar.gz"

find backups -name 'welfare-*.sql.gz' -mtime +"$KEEP_DAYS" -delete
find backups -name 'files-*.tar.gz' -mtime +"$KEEP_DAYS" -delete

echo "$(date '+%F %T') backed up: $(ls -1 backups/*"$STAMP"* | tr '\n' ' ')"

# Restore (stop the web service first: docker compose stop web):
#   gunzip -c backups/welfare-<date>.sql.gz | docker compose exec -T db psql -U welfare welfare
#   docker compose exec -T web tar -C /app -xzf - < backups/files-<date>.tar.gz
