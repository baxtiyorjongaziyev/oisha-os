"""
User client connection and main entrypoint runner.
"""
import asyncio
import logging
import os
from telethon import TelegramClient

from src.settings import settings
from src.context import app_ctx
from src.boot import boot_application
from src.entrypoint.daemon_tasks import _restore_cloud_artifacts

logger = logging.getLogger("OishaRunner")

async def _connect_user_client(telegram_client: TelegramClient) -> bool:
    from src.services.core.agent_runtime import resolve_runtime_mode

    if resolve_runtime_mode().control_plane_only:
        logger.info("[AUTH] Skipping userbot login: control-plane-only runtime")
        return False

    """Connect the userbot without ever falling back to interactive auth.
    
    Args:
        telegram_client: The Telethon client instance to connect
        
    Returns:
        bool: True if authorized, False otherwise
    """
    try:
        await telegram_client.connect()
    except Exception as exc:
        error_fingerprint = f"{type(exc).__name__} {exc}".upper()
        duplicate_markers = (
            "AUTH_KEY_DUPLICATED",
            "AUTHKEYDUPLICATEDERROR",
            "AUTHORIZATION KEY",
            "USED UNDER TWO DIFFERENT IP",
        )
        if any(marker in error_fingerprint for marker in duplicate_markers):
            logger.error("[AUTH] Userbot session is already in use by another runtime.")
            try:
                await telegram_client.disconnect()
            except Exception as disconnect_exc:
                logger.warning(
                    f"[AUTH] Could not disconnect invalid userbot session: {disconnect_exc}"
                )
            try:
                import src.api_server as api_module

                api_module.update_api_status(
                    "degraded", "Userbot session delegated to another runtime"
                )
                api_module.set_runtime_context(userbot_authorized=False)
            except (ImportError, AttributeError) as api_exc:
                logger.warning(f"[AUTH] Could not update API status: {api_exc}")
            return False
        raise

    if await telegram_client.is_user_authorized():
        return True

    # Only an explicit local terminal may prompt for Telegram login.
    # Production VMs run under systemd, so prompting there causes EOFError
    # and makes health checks pass briefly before the process dies.
    cloud_control_plane = bool(os.getenv("K_SERVICE"))
    interactive_auth_allowed = (
        os.getenv("ALLOW_LOCAL_RUN") == "1"
        and sys.stdin is not None
        and sys.stdin.isatty()
    )
    if not cloud_control_plane and interactive_auth_allowed:
        logger.info(
            "[AUTH] Interactive auth allowed for local runtime. Please follow the prompts in your terminal."
        )
        await telegram_client.start()
        if await telegram_client.is_user_authorized():
            # Export session string for the user convenient copy-pasting
            new_string = telegram_client.session.save()
            print("\n" + "=" * 50)
            print("🚀 [SUCCESS] NEW SESSION STRING GENERATED:")
            print(new_string)
            print("=" * 50 + "\n")
            return True

    logger.error(
        "[AUTH] Userbot session missing or unauthorized. Interactive auth is disabled in cloud runtime."
    )
    return False


async def main():
    """Botlarni ishga tushirish (Userbot + Admin Bot)."""
    from src.boot import boot_application
    await boot_application()

