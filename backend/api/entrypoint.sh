#!/usr/bin/env sh
set -e

echo "[entrypoint] applying Alembic migrations"
alembic upgrade head

echo "[entrypoint] starting uvicorn"
# Render (and most PaaS) set PORT; local docker-compose defaults to 8000.
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
