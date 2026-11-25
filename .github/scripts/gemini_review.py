"""Post a Gemini PR review comment. Reads PR diff, calls Gemini API, upserts one comment."""
import json
import os
import subprocess
import sys
import urllib.request

MARKER = "<!-- gemini-pr-review -->"
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
MAX_DIFF = 120_000


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def main() -> int:
    pr, repo, key = os.environ["PR"], os.environ["REPO"], os.environ["GEMINI_API_KEY"]
    diff = gh("pr", "diff", pr, "--repo", repo)
    if not diff.strip():
        return 0
    guide = ""
    if os.path.exists(".gemini/styleguide.md"):
        guide = open(".gemini/styleguide.md", encoding="utf-8").read()
    prompt = (
        "You are a strict senior reviewer. Report only real bugs, security issues and data-loss risks "
        "in this pull request diff. Skip style nits. For each finding give file:line, severity "
        "(high/medium), the problem and a concrete fix. If nothing is wrong, reply exactly 'No issues found.'\n\n"
        f"Project rules:\n{guide}\n\nDiff:\n{diff[:MAX_DIFF]}"
    )
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:  # nosec B310 - fixed https URL
        data = json.load(resp)
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    body = f"{MARKER}\n### Gemini review ({MODEL})\n\n{text}"
    if len(diff) > MAX_DIFF:
        body += "\n\n_Diff truncated; review covers the first part only._"
    existing = gh("api", f"repos/{repo}/issues/{pr}/comments", "--paginate",
                  "--jq", f'.[] | select(.body | startswith("{MARKER}")) | .id').split()
    if existing:
        gh("api", "-X", "PATCH", f"repos/{repo}/issues/comments/{existing[-1]}", "-f", f"body={body}")
    else:
        gh("pr", "comment", pr, "--repo", repo, "--body", body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
