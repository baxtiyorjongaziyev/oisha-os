"""Print which .env keys are set, never their values.

Usage: python scripts/env_status.py PREFIX [PREFIX ...] [--file PATH]
Output: KEY=<set> | KEY=<empty>. Boolean-ish flags (0/1/true/false) are shown
as-is because they are not secrets. This is the sanctioned way for agents to
inspect .env (see .claude/hooks/guard.py).
"""
import sys
from pathlib import Path

FLAG_VALUES = {"0", "1", "true", "false", "yes", "no", "on", "off"}


def main(argv: list[str]) -> int:
    path = Path(".env")
    if "--file" in argv:
        i = argv.index("--file")
        path = Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    prefixes = argv or [""]
    if not path.is_file():
        print(f"{path}: not found", file=sys.stderr)
        return 1
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.removeprefix("export ").strip()
        if not any(key.startswith(p) for p in prefixes):
            continue
        value = value.strip().strip("'\"")
        if value.lower() in FLAG_VALUES:
            shown = value
        else:
            shown = "<set>" if value else "<empty>"
        print(f"{key}={shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
