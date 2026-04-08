#!/bin/sh

# [GOD MODE] Cloud Entrypoint for Oisha-OS
echo "👸 Oisha-OS: Preparing 24/7 Cloud Environment..."

# 1. Mount GCS Bucket for persistent Telegram sessions
# This allows the .session file to survive Cloud Run restarts.
if [ -n "$GCS_BUCKET" ]; then
    echo "📦 Mounting GCS Bucket $GCS_BUCKET to /app/data..."
    mkdir -p /app/data
    gcsfuse --only-dir data $GCS_BUCKET /app/data
    if [ $? -eq 0 ]; then
        echo "✅ GCS Bucket mounted successfully."
    else
        echo "⚠️ GCS Bucket mounting failed. Continuing with local data storage..."
    fi
else
    echo "ℹ️ GCS_BUCKET not set. Persistent sessions might be lost on restart."
fi

# 2. Start the main bot
echo "🚀 Oisha-OS: Igniting God Mode Agents..."
exec python src/main.py
