#!/bin/sh
set -e

# Oisha-OS Cloud Run entrypoint
# ------------------------------
# GCS Fuse bloki olib tashlandi (commit b490c77: Cloud Run managed gcsfuse'ni
# qo'llab-quvvatlamaydi). Persistent storage endi Turso'da (src/database.py
# TursoAdapter orqali). TURSO_DATABASE_URL + TURSO_AUTH_TOKEN env'lari
# deploy.yml'da bind qilingan.

echo "Oisha-OS: boot sequence starting..."

if [ -n "$TURSO_DATABASE_URL" ]; then
    echo "[persistence] Turso cloud DB detected (restart-safe)."
else
    echo "[persistence] WARNING: TURSO_DATABASE_URL not set — using ephemeral SQLite. Data lost on restart."
fi

echo "Oisha-OS: igniting agents..."
exec python -u src/main.py
