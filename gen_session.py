"""Refuse local userbot session creation.

The production Telethon session is owned by Oracle VM. Session rotation must use
the production runbook so reusable credentials never reach local terminal logs.
"""


def main() -> int:
    """Exit safely and point operators to the approved production workflow."""
    print(
        "Local Telegram session generation is disabled. "
        "Use docs/operations/telethon-session-ownership.md on Oracle VM."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
