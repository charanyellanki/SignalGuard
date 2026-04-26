#!/usr/bin/env sh
set -e

echo "[entrypoint] applying Alembic migrations"
alembic upgrade head

echo "[entrypoint] starting uvicorn"
exec uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers
