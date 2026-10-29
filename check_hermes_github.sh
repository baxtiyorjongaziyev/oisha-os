#!/bin/bash
set -euo pipefail
GITHUB_TOKEN="$(sed -n 's/^GITHUB_TOKEN=//p' /home/hermes/.hermes/.env)"
test -n "$GITHUB_TOKEN" || { echo GITHUB_TOKEN_MISSING; exit 1; }
curl -sS --max-time 20 -o /tmp/hermes-gh-user.json -w 'USER_HTTP=%{http_code}\n' -H "Authorization: Bearer ${GITHUB_TOKEN}" -H 'Accept: application/vnd.github+json' https://api.github.com/user
cat /tmp/hermes-gh-user.json | python3 -c 'import json,sys; d=json.load(sys.stdin); print("GITHUB_API_OK login="+str(d.get("login"))+" id="+str(d.get("id")))'
curl -sS --max-time 20 -o /tmp/hermes-gh-repos.json -w 'REPOS_HTTP=%{http_code}\n' -H "Authorization: Bearer ${GITHUB_TOKEN}" -H 'Accept: application/vnd.github+json' 'https://api.github.com/user/repos?per_page=100&sort=updated'
cat /tmp/hermes-gh-repos.json | python3 -c 'import json,sys; a=json.load(sys.stdin); print("REPO_COUNT_PAGE="+str(len(a))); [print(x.get("full_name"), "private="+str(x.get("private"))) for x in a]'
