"""Automated PR bug review using Gemini API for GitHub Actions.

Reads a unified git diff (from stdin or --diff-file), filters out noisy
lock/generated files, asks Gemini to find concrete bugs/security issues,
and outputs a Markdown review report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MARKER = "<!-- oisha-ai-bug-review -->"
DEFAULT_MODEL = "gemini-3.8-flash"
RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
MAX_DIFF_CHARS = 60_000
IGNORED_SUFFIXES = (
    ".lock",
    "pnpm-lock.yaml",
    "package-lock.json",
    "yarn.lock",
    ".min.js",
    ".min.css",
    ".svg",
    ".png",
    ".jpg",
    ".pdf",
)

SYSTEM_PROMPT = """You are a senior software engineer performing an automated bug and security review on a GitHub Pull Request diff.

Focus ONLY on real, actionable issues:
1. Logic bugs, race conditions, off-by-one errors, None/null crashes.
2. Security vulnerabilities (injection, auth bypass, secret leaks, unsafe subprocess/eval).
3. Async/concurrency bugs (blocking I/O inside async def, missing await).
4. Regressions or broken edge cases.

Rules:
- Do NOT comment on formatting, style, or trivial naming unless it causes a bug.
- Be concise. For each finding, include: severity (`CRITICAL`, `HIGH`, `MEDIUM`), file path, line/symbol, what can break, and a concrete fix.
- If no real bugs are found, reply with a short confirmation: "✅ No concrete bugs or security issues found in this diff."
- Write the summary in concise Uzbek (Latin) with technical terms in English.
"""


def filter_diff(raw_diff: str, max_chars: int = MAX_DIFF_CHARS) -> str:
    """Drop noisy/generated file sections and truncate to max_chars."""
    sections = raw_diff.split("diff --git ")
    kept: list[str] = []
    for section in sections:
        if not section.strip():
            continue
        header = section.splitlines()[0]
        if any(suffix in header for suffix in IGNORED_SUFFIXES):
            continue
        kept.append("diff --git " + section)

    combined = "".join(kept)
    if len(combined) > max_chars:
        combined = (
            combined[:max_chars]
            + "\n\n... [diff truncated at "
            + str(max_chars)
            + " chars] ...\n"
        )
    return combined


def call_gemini(diff_text: str, api_key: str, model: str = DEFAULT_MODEL) -> str:
    """Call Gemini generateContent REST API and return markdown text."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "Review the following Pull Request diff for bugs "
                            "and security issues:\n\n```diff\n"
                            f"{diff_text}\n```"
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    body = None
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310
                body = json.loads(resp.read().decode("utf-8"))
                break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            last_exc = RuntimeError(f"Gemini API HTTP {exc.code}: {detail}")
            if exc.code in RETRYABLE_HTTP_CODES and attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            raise last_exc from exc
    if body is None:
        raise last_exc or RuntimeError("Gemini API request failed")

    candidates = body.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini API returned no candidates")
    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise RuntimeError("Gemini API returned empty text")
    return text


def format_comment(review_body: str, model: str) -> str:
    """Wrap review output with a sticky HTML marker."""
    return (
        f"{MARKER}\n"
        f"### AI Bug Review (`{model}`)\n\n"
        f"{review_body}\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI PR bug review via Gemini")
    parser.add_argument("--diff-file", type=Path, help="Path to unified diff file")
    parser.add_argument("--output-file", type=Path, help="Write markdown comment here")
    parser.add_argument(
        "--model",
        default=os.environ.get("GEMINI_REVIEW_MODEL", DEFAULT_MODEL),
        help="Gemini model name",
    )
    args = parser.parse_args(argv)

    api_key = (
        os.environ.get("GEMINI_REVIEW_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or ""
    ).strip()
    if not api_key:
        print("GEMINI_REVIEW_API_KEY / GEMINI_API_KEY topilmadi, skip.", file=sys.stderr)
        return 0

    raw_diff = (
        args.diff_file.read_text(encoding="utf-8", errors="replace")
        if args.diff_file
        else sys.stdin.read()
    )
    filtered = filter_diff(raw_diff)
    if not filtered.strip():
        report = format_comment(
            "Koʻrib chiqiladigan kod oʻzgarishlari topilmadi (faqat lock/asset fayllar).",
            args.model,
        )
    else:
        try:
            review = call_gemini(filtered, api_key=api_key, model=args.model)
        except RuntimeError as exc:
            if any(f"HTTP {code}" in str(exc) for code in RETRYABLE_HTTP_CODES):
                print(f"Gemini API vaqtincha band, review oʻtkazib yuborildi: {exc}", file=sys.stderr)
                return 0
            raise
        report = format_comment(review, args.model)

    if args.output_file:
        args.output_file.write_text(report, encoding="utf-8")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
