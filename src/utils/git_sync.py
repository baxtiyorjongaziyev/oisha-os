import asyncio
import logging
import os
from pathlib import Path
from src.settings import settings

logger = logging.getLogger("git_sync")

async def push_vault_to_remote(vault_path: Path) -> None:
    """Git add/commit/push the Obsidian vault.
    If a GITHUB_TOKEN is set, it is exported as GIT_HTTPS_TOKEN for git.
    """
    env = os.environ.copy()
    if getattr(settings, "GITHUB_TOKEN", None):
        token = settings.GITHUB_TOKEN
        if isinstance(token, type(settings.GITHUB_TOKEN)):
            token_val = token.get_secret_value()
        else:
            token_val = str(token)
        if token_val:
            env["GIT_HTTPS_TOKEN"] = token_val
    vault_path_str = str(vault_path)

    async def run(*args: str) -> tuple[int, bytes, bytes]:
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", vault_path_str, *args,
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
