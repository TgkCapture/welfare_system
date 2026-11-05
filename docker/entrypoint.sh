#!/bin/sh
# Bring the database up to date, then start the command (gunicorn by default).
# Set SKIP_MIGRATIONS=1 to start without upgrading, e.g. for a one-off shell.
set -e

if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
    echo "Upgrading the database…"
    ENABLE_AUTO_CLEANUP=false flask db upgrade
fi

exec "$@"
