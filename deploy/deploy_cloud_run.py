"""Deprecated full-runtime Cloud Run deploy entrypoint.

The old implementation copied every ``.env`` value into a command line and
attempted to run the Telethon userbot on Cloud Run.  Both behaviours violate
the approved two-head architecture.  Keep this guard so old bookmarks fail
closed and point operators to the secret-safe deployment path.
"""

from __future__ import annotations


def deploy() -> None:
    raise SystemExit(
        "Full Oisha Cloud Run deployment is disabled. "
        "Use scripts/deploy_aiogram_cloudrun.ps1 after owner approval."
    )


if __name__ == "__main__":
    deploy()
