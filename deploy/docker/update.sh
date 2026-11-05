#!/bin/sh
# Install a new version. Run from the app's folder:
#
#   sh deploy/docker/update.sh v3.0.1        (a tag, branch or commit; default: main)
#
# Backs up first, rebuilds, restarts (the entrypoint upgrades the database),
# then waits for the health check. To go back, run it again with the
# previous version; if a migration changed the database, restore the backup.
set -eu

REF="${1:-main}"
PREVIOUS="$(git rev-parse --short HEAD)"

echo "== Backing up"
sh deploy/docker/backup.sh

echo "== Fetching $REF (now at $PREVIOUS)"
git fetch --tags origin
git checkout --quiet "$REF"
if git show-ref --verify --quiet "refs/remotes/origin/$REF"; then
    git merge --quiet --ff-only "origin/$REF"        # a branch: bring it up to date
fi

echo "== Building and restarting"
APP_VERSION="$(git describe --tags --always)" docker compose up -d --build

echo "== Waiting for the health check"
for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8000/api/health 2>/dev/null; then
        echo
        echo "Updated from $PREVIOUS to $(git rev-parse --short HEAD)."
        exit 0
    fi
    sleep 3
done
echo "The app didn't come up healthy. See: docker compose logs --tail 100 web"
echo "To go back: sh deploy/docker/update.sh $PREVIOUS"
exit 1
