import asyncio
import base64
import logging
import os
import shutil
from pathlib import Path
from src.settings import settings

logger = logging.getLogger("git_sync")


def _apply_github_token_env(env: dict[str, str], token_val: str) -> None:
    """Attach GitHub HTTPS header auth and legacy GIT_HTTPS_TOKEN to subprocess env."""
    env["GIT_HTTPS_TOKEN"] = token_val
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    basic = base64.b64encode(f"x-access-token:{token_val}".encode("utf-8")).decode("ascii")
    idx = int(env.get("GIT_CONFIG_COUNT", "0") or "0")
    # Reset prior extraheader entries (multivar) before adding our Authorization header.
    env["GIT_CONFIG_COUNT"] = str(idx + 2)
    env[f"GIT_CONFIG_KEY_{idx}"] = "http.https://github.com/.extraheader"
    env[f"GIT_CONFIG_VALUE_{idx}"] = ""
    env[f"GIT_CONFIG_KEY_{idx + 1}"] = "http.https://github.com/.extraheader"
    env[f"GIT_CONFIG_VALUE_{idx + 1}"] = f"AUTHORIZATION: basic {basic}"


def _git_bin() -> str | None:
    """``git`` ijro etuvchi faylini topadi.

    systemd unit ``PATH`` ni faqat venv'ga cheklab qo'yган bo'lishi mumkin
    (Oracle VM'da aynan shunday: ``PATH=/home/ubuntu/oisha-os/venv/bin``),
    o'shanda ``create_subprocess_exec("git", ...)`` ``FileNotFoundError``
    beradi va Second Brain digest jimgina yiqiladi. Avval PATH'dan, keyin
    keng tarqalgan absolyut joylardan qidiramiz.
    """
    found = shutil.which("git")
    if found:
        return found
    for candidate in ("/usr/bin/git", "/usr/local/bin/git", "/bin/git"):
        if os.path.exists(candidate):
            return candidate
    return None

async def push_vault_to_remote(vault_path: Path) -> None:
    """Git add/commit/push the Obsidian vault.
    If a GITHUB_TOKEN is set, it is exported as GIT_HTTPS_TOKEN for git.
    """
    env = os.environ.copy()
    token = getattr(settings, "GITHUB_TOKEN", None)
    if token:
        token_val = (
            token.get_secret_value()
            if hasattr(token, "get_secret_value")
            else str(token)
        ).strip()
        if token_val:
            _apply_github_token_env(env, token_val)
    vault_path_str = str(vault_path)

    git_bin = _git_bin()
    if not git_bin:
        logger.warning(
            "[GIT_SYNC] 'git' topilmadi (PATH=%s) — vault push o'tkazib yuborildi",
            env.get("PATH", ""),
        )
        return

    async def run(*args: str) -> tuple[int, bytes, bytes]:
        proc = await asyncio.create_subprocess_exec(
            git_bin, "-C", vault_path_str, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        out, err = await proc.communicate()
        return proc.returncode, out, err

    rc, _, err = await run("add", ".")
    if rc != 0:
        logger.error(f"Git add failed: {err.decode().strip()}")
        return

    rc, out, err = await run("commit", "-m", f"Second Brain digest – {settings.APP_TIMEZONE}")
    if rc != 0:
        # Nothing to commit is not an error — skip the push quietly.
        combined = (out + b"\n" + err).decode(errors="replace").lower()
        if "nothing to commit" in combined:
            logger.info("Vault has no changes to push.")
            return
        logger.error(f"Git commit failed: {combined.strip()}")
        return

    rc, _, err = await run("push", settings.VAULT_GIT_REMOTE, settings.VAULT_GIT_BRANCH)
    if rc != 0:
        logger.error(f"Git push failed: {err.decode().strip()}")
    else:
        logger.info("Vault successfully pushed to remote.")
