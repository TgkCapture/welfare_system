#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting Mzugoss Welfare Flask App..."

# Ensure upload and report folders exist
mkdir -p /app/uploads
mkdir -p /app/reports

# Fix permissions 
chmod -R 755 /app/uploads /app/reports

# Export environment variables for Flask
export FLASK_APP=run.py
export FLASK_ENV=production

# Run the Flask app
echo "Running Flask on 0.0.0.0:5000"
flask run --host=0.0.0.0 --port=5000