#!/bin/sh
# Install a new version on a server without Docker (with Docker, use
# deploy/docker/update.sh). Run from the app's folder:
#
#   sh deploy/update.sh v3.0.1        (a tag, branch or commit; default: main)
#
# Backs up, installs the requirements, upgrades the database, restarts the
# service and waits for the health check. To go back, run it again with the
# previous version; if a migration changed the database, restore the backup.
set -eu

REF="${1:-main}"
# A tag, branch or commit name only: this may come from the deploy key's forced command
case "$REF" in
    -*|*[!A-Za-z0-9._/-]*|'') echo "Not a version name: $REF" >&2; exit 2 ;;
esac
SERVICE="${SERVICE:-welfare3}"
PORT="${PORT:-5001}"
PREVIOUS="$(git rev-parse --short HEAD)"

echo "== Backing up"
sh deploy/backup.sh

echo "== Fetching $REF (now at $PREVIOUS)"
git fetch --tags origin
git checkout --quiet "$REF"
if git show-ref --verify --quiet "refs/remotes/origin/$REF"; then
    git merge --quiet --ff-only "origin/$REF"        # a branch: bring it up to date
fi

echo "== Installing requirements"
venv/bin/pip install --quiet -r requirements.txt

echo "== Upgrading the database"
sh deploy/flask.sh db upgrade

echo "== Restarting $SERVICE"
sudo systemctl restart "$SERVICE"

for _ in $(seq 1 20); do
    if curl -fsS "http://127.0.0.1:$PORT/api/health" 2>/dev/null; then
        echo
        echo "Updated from $PREVIOUS to $(git rev-parse --short HEAD)."
        exit 0
    fi
    sleep 3
done
echo "The app didn't come up healthy. See: journalctl -u $SERVICE -n 100"
echo "To go back: sh deploy/update.sh $PREVIOUS"
exit 1
