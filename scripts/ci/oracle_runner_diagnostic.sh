#!/usr/bin/env bash
set -euo pipefail

workspace="${GITHUB_WORKSPACE:-.}"

printf 'runner_name=%s\n' "${RUNNER_NAME:-unknown}"
printf 'runner_os=%s\n' "${RUNNER_OS:-unknown}"
printf 'runner_arch=%s\n' "${RUNNER_ARCH:-unknown}"
printf 'workspace_writable=%s\n' "$(test -w "$workspace" && echo true || echo false)"
printf 'disk_free_kb=%s\n' "$(df -Pk "$workspace" | awk 'NR==2 {print $4}')"
printf 'docker_available=%s\n' "$(command -v docker >/dev/null 2>&1 && echo true || echo false)"
printf 'python_available=%s\n' "$(command -v python3 >/dev/null 2>&1 && echo true || echo false)"
printf 'git_available=%s\n' "$(command -v git >/dev/null 2>&1 && echo true || echo false)"
