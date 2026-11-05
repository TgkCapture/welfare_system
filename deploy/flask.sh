#!/bin/sh
# Run a flask command with the app's settings from .env, on a server
# without Docker. Run from the app's folder:
#
#   sh deploy/flask.sh list-users --group mzugoss
#   sh deploy/flask.sh reset-password --group mzugoss --email chair@example.com
#   sh deploy/flask.sh db upgrade
set -eu

if [ -f .env ]; then
    # KEY=value lines, as systemd reads them: values may contain spaces
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in ''|\#*) continue ;; esac
        export "$line"
    done < .env
fi
# One-off commands never start the daily cleanup thread; the service runs it
export FLASK_APP=run.py FLASK_ENV="${FLASK_ENV:-production}" ENABLE_AUTO_CLEANUP=false
exec venv/bin/flask "$@"
