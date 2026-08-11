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
    cmd = (
        f'git -C "{vault_path}" add . && '
        f'git -C "{vault_path}" commit -m "Second Brain digest – {settings.APP_TIMEZONE}" && '
        f'git -C "{vault_path}" push {settings.VAULT_GIT_REMOTE} {settings.VAULT_GIT_BRANCH}'
    )
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        logger.error(f"Git push failed: {err.decode().strip()}")
    else:
        logger.info("Vault successfully pushed to remote.")
