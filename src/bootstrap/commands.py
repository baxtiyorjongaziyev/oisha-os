"""
API Command Processor and Negotiation Helpers for Oisha-OS Bootstrap.
"""
import asyncio
import logging
import os

from src.api.routes.state import api_state
from src.context import app_ctx

logger = logging.getLogger("OishaBootstrap")


def _negotiation_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


async def _command_processor():
    """Processes commands from the API Server (e.g. sending messages)."""
    logger.info("[COMMANDS] API Command Processor started.")
    while True:
        try:
            item = await api_state.command_queue.get()
            cmd = item.get("cmd")
            logger.info(f"[COMMANDS] Received: {cmd}")

            if cmd == "send_message":
                u_id = item.get("user_id")
                txt = item.get("text")
                target_client = app_ctx.bot_client or app_ctx.client
                if target_client:
                    try:
                        await target_client.send_message(u_id, txt)
                        logger.info(f"[COMMANDS] Message sent to {u_id}")
                        await app_ctx.msg_controller.db.log_message(u_id, txt, is_ai=True)
                    except Exception as e:
                        logger.error(f"[COMMANDS] Failed to send msg to {u_id}: {e}")

            elif cmd == "audit":
                if app_ctx.audit_agent:
                    asyncio.create_task(app_ctx.audit_agent.run_full_audit())
                    logger.info("[COMMANDS] Full audit triggered.")

            api_state.command_queue.task_done()
        except Exception as e:
            logger.error(f"[COMMANDS] Processor error: {e}")
            await asyncio.sleep(1)


async def _surgical_send(user_id: int, text: str):
    logger.info("[SURGICAL] Proactive customer send blocked by owner policy.")
    return None
