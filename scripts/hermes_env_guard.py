"""Hermes (Amina AI) Telegram group noise guards.

Ensures Amina never free-responds to unaddressed chatter in Sotuv Bolim or other
team groups while still passively observing context and responding to @mentions,
replies, or explicit "Amina" wake-words.
"""
from __future__ import annotations

import logging
import os
import pathlib
import subprocess

logger = logging.getLogger("hermes_env_guard")

HERMES_TELEGRAM_GUARD_VARS: dict[str, str] = {
    "TELEGRAM_FREE_RESPONSE_TOPICS": "",
    "TELEGRAM_FREE_RESPONSE_CHATS": "",
    "TELEGRAM_REQUIRE_MENTION": "true",
    "TELEGRAM_BOTS_REQUIRE_MENTION": "true",
    "TELEGRAM_OBSERVE_UNMENTIONED_GROUP_MESSAGES": "true",
    "TELEGRAM_MENTION_PATTERNS": '["(?i)(?<![\\\\w@])(?:amina|амина)(?:xon|jon)?\\\\b"]',
}


def enforce_hermes_telegram_guards(
    env_path: pathlib.Path,
    *,
    owner_user: str | None = "hermes",
) -> bool:
    """Update Hermes .env in-place so free-response topics stay disabled."""
    if not env_path.is_file():
        return False
    try:
        raw_lines = env_path.read_text(encoding="utf-8").splitlines()
        seen: set[str] = set()
        updated_lines: list[str] = []
        for line in raw_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in HERMES_TELEGRAM_GUARD_VARS:
                    updated_lines.append(f"{key}={HERMES_TELEGRAM_GUARD_VARS[key]}")
                    seen.add(key)
                    continue
            updated_lines.append(line)

        for key, val in HERMES_TELEGRAM_GUARD_VARS.items():
            if key not in seen:
                updated_lines.append(f"{key}={val}")

        env_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
        if owner_user and os.name != "nt":
            subprocess.run(
                ["chown", f"{owner_user}:{owner_user}", str(env_path)],
                check=False,
            )  # nosec B603 B607
        logger.info("[Hermes] Telegram mention guardlar tekshirildi: %s", env_path)
        return True
    except OSError as exc:
        logger.warning("[Hermes] .env guard yangilanmadi (%s): %s", env_path, exc)
        return False
