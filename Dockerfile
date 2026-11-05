# Welfare system: one image serving every group.
#
#   docker compose up -d          # app + Postgres + Redis, see docker-compose.yml
#
# The container upgrades the database on start, then runs gunicorn.
# Uploaded files, reports, logs and group logos live in volumes.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FLASK_APP=run.py \
    FLASK_ENV=production

WORKDIR /app

# Dependencies first, so code changes don't reinstall them
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Run as an ordinary user; it owns only the folders the app writes to
RUN useradd --create-home --uid 1000 welfare \
    && mkdir -p uploads reports logs instance/branding \
    && chown -R welfare:welfare uploads reports logs instance \
    && chmod +x docker/entrypoint.sh
USER welfare

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["sh", "-c", "exec gunicorn 'app:create_app()' --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-2} --timeout 120 --access-logfile -"]
