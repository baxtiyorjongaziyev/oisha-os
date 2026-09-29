"""PreToolUse guard for Claude Code agents working on Oisha-OS.

Blocks actions that CLAUDE.md / AGENTS.md forbid, so the rules are enforced
mechanically instead of relying on the model to remember them.
Exit code 2 = block (stderr is shown to the agent). Exit 0 = allow.
"""
import json
import re
import sys

BASH_RULES = [
    (r"\bpython[\w.]*\s+(-m\s+)?src[/\\.]main(\.py)?\b|\bsrc[/\\](userbot|admin_bot)\.py\b",
     "Local userbot run forbidden: Oracle VM owns the Telegram session (AuthKeyDuplicatedError)."),
    # [^;&|\n]* keeps the match inside the single `git push` command segment
    (r"\bgit\s+push\b[^;&|\n]*(--force\b|--force-with-lease\b|\s-f\b)",
     "Force push is blocked. Push normally or ask the owner."),
    (r"\bgit\s+push\b[^;&|\n]*\s(\S+:)?(main|master)\b",
     "Direct push to main is blocked. Open a PR from a feat/ or fix/ branch."),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard is blocked. Use a WIP commit or git revert."),
    (r"\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r", "rm -rf is blocked."),
    # only file-access commands / redirects, so mentioning ".env" in text (PR bodies) is fine
    (r"(\b(cat|type|less|more|head|tail|source|get-content|gc|cp|copy|mv|move|nano|vim?|code|sed|awk|grep)\b"
     r"[^;&|\n]*|>>?\s*)(^|[\s/\\'\"])\.env(\s|$|['\"])",
     "Reading or writing .env is blocked (secrets)."),
    (r"\.session\b", "Telethon .session files are off-limits."),
]

PATH_RULES = [
    (r"(^|[/\\])\.env$", "Editing/reading .env is blocked (secrets). Use .env.example."),
    (r"\.session$", "Telethon .session files are off-limits."),
]


def check(tool: str, data: dict) -> str | None:
    if tool == "Bash" or tool == "PowerShell":
        cmd = data.get("command", "")
        for pattern, msg in BASH_RULES:
            if re.search(pattern, cmd, re.IGNORECASE):
                return msg
    if tool in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = data.get("file_path", "") or data.get("notebook_path", "")
        for pattern, msg in PATH_RULES:
            if re.search(pattern, path, re.IGNORECASE):
                return msg
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    reason = check(event.get("tool_name", ""), event.get("tool_input", {}) or {})
    if reason:
        print(f"BLOCKED by .claude/hooks/guard.py: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
