#!/usr/bin/env bash
set -euo pipefail

MODEL="${OLLAMA_TEXT_MODEL:-qwen2.5:3b}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "[OLLAMA] Installing local fallback runtime"
  curl -fsSL https://ollama.com/install.sh | sh
fi

if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl enable --now ollama
fi

for _ in $(seq 1 20); do
  if curl -fsS --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null; then
    break
  fi
  sleep 2
done

if ! curl -fsS --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null; then
  echo "[OLLAMA] Runtime did not become ready" >&2
  exit 1
fi

if ! ollama list | awk 'NR > 1 {print $1}' | grep -Fxq "$MODEL"; then
  echo "[OLLAMA] Pulling $MODEL"
  ollama pull "$MODEL"
fi

echo "[OLLAMA] Ready with $MODEL"
