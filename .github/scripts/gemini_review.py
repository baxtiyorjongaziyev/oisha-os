"""Post a Gemini PR review comment. Reads PR diff, calls Gemini API, upserts one comment."""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

MARKER = "<!-- gemini-pr-review -->"
MODEL = os.environ.get("GEMINI_MODEL", "")
API = "https://generativelanguage.googleapis.com/v1beta"
MAX_DIFF = 120_000


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def _call(url: str, key: str, payload=None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # nosec B310 - fixed https URL
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        print(f"Gemini API {exc.code}: {exc.read().decode(errors='replace')[:300]}", file=sys.stderr)
        raise


def candidate_models(key: str) -> list[str]:
    """Flash models supporting generateContent, newest first (or GEMINI_MODEL if set)."""
    if MODEL:
        return [MODEL]
    models = _call(f"{API}/models?pageSize=200", key).get("models", [])
    names = [
        m["name"].split("/", 1)[1] for m in models
        if "generateContent" in m.get("supportedGenerationMethods", [])
        and "flash" in m["name"] and not any(x in m["name"] for x in ("lite", "image", "tts", "live", "exp", "preview"))
    ]
    if not names:
        raise SystemExit("No suitable Gemini Flash model available")
    return sorted(names, reverse=True)


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
    data, model = None, ""
    for model in candidate_models(key):
        try:
            data = _call(f"{API}/models/{model}:generateContent", key, {"contents": [{"parts": [{"text": prompt}]}]})
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in (404, 429):
                raise
            print(f"skip {model}: HTTP {exc.code}", file=sys.stderr)
    if data is None:
        raise SystemExit("No Gemini model accepted the request (quota or availability)")
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    body = f"{MARKER}\n### Gemini review ({model})\n\n{text}"
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
