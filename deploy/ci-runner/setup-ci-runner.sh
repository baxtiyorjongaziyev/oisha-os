#!/usr/bin/env bash
# Isolated GitHub Actions runner for UNTRUSTED pull-request jobs.
#
# Why: GitHub-hosted minutes are billed, and PR code must never run on the
# production runner (label "oracle"), which can read prod secrets/sessions.
# This runner lives in a throwaway Docker container with:
#   - its own label "ci-sandbox" (never "oracle")
#   - no host volumes (no access to /home/ubuntu/oisha-os, .env, sessions)
#   - registration token only (no long-lived PAT inside the container, so a
#     PR job cannot steal repo-admin credentials). Non-ephemeral on purpose:
#     an ephemeral runner would need a PAT to re-register after every job.
#   - CPU/RAM caps so tests cannot starve production
#
# Usage (on the server, as a sudo user, once):
#   GH_RUNNER_TOKEN=<registration token> bash deploy/ci-runner/setup-ci-runner.sh
# Get the token: GitHub -> repo Settings -> Actions -> Runners ->
#   New self-hosted runner -> copy the token from the "config" command.
#   (It expires after 1 hour; do not commit it anywhere.)
set -euo pipefail

: "${GH_RUNNER_TOKEN:?set GH_RUNNER_TOKEN (registration token, valid 1h)}"
REPO_URL="${REPO_URL:-https://github.com/baxtiyorjongaziyev/oisha-os}"
NAME="${RUNNER_NAME:-ci-sandbox}"
IMAGE="myoung34/github-runner:2.329.0"

command -v docker >/dev/null || { echo "Docker kerak: sudo apt-get install -y docker.io"; exit 1; }

sudo docker rm -f "$NAME" >/dev/null 2>&1 || true
sudo docker run -d --name "$NAME" \
  --restart unless-stopped \
  --cpus 1.5 --memory 2g --pids-limit 512 \
  --security-opt no-new-privileges \
  -e REPO_URL="$REPO_URL" \
  -e RUNNER_TOKEN="$GH_RUNNER_TOKEN" \
  -e RUNNER_NAME="$NAME" \
  -e LABELS="ci-sandbox" \
  -e RUNNER_SCOPE=repo \
  -e EPHEMERAL=true \
  -e DISABLE_AUTO_UPDATE=true \
  "$IMAGE"

echo "OK: '$NAME' konteyneri ishga tushdi. GitHub -> Settings -> Actions -> Runners da 'Idle' ko'rinishi kerak."
echo "Keyingi qadam: PR job'larida runs-on: [self-hosted, ci-sandbox] ga o'tish (alohida PR)."
