"""
Telegram dialog entity resolution and temporary contact cleanup mixin.
"""
from __future__ import annotations

import inspect
import re
from typing import Any, Optional
import structlog

from src.services.core.telegram.temp_contacts import delete_temp_contact, import_temp_contact

logger = structlog.get_logger()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class DialogResolverMixin:
    """Resolves Telegram chats and fetches messages across direct and group chats."""

    @staticmethod
    def _normalise_phone(value: str) -> str:
        digits = re.sub(r"\D", "", str(value or ""))
        if len(digits) == 9:
            digits = "998" + digits
        return digits

    async def _resolve_dialog_entity(self, phone_or_username: str) -> tuple[Any, Optional[int]]:
        """Resolve cached peers first, then temporarily import a phone contact."""
        clean_phone = self._normalise_phone(phone_or_username)
        is_phone_lookup = bool(clean_phone) and len(clean_phone) >= 9
        if is_phone_lookup and self._telegram_cooldown_remaining():
            return None, None
        try:
            return await self.user_client.get_input_entity(phone_or_username), None
        except Exception as first_error:
            logger.debug("[TELEGRAM_TASK] Direct entity resolution missed for %s: %s", phone_or_username, first_error)
            error_text = str(first_error).lower()
            if (
                "flood" in error_text
                or "getcontactsrequest" in error_text
                or "wait of" in error_text
            ):
                raise first_error
            if not clean_phone:
                raise first_error

        user, newly_imported = await import_temp_contact(self.user_client, clean_phone)
        if user is None:
            return None, None
        temp_id = int(user.id) if newly_imported else None
        try:
            return await self.user_client.get_input_entity(user), temp_id
        except Exception:
            await delete_temp_contact(self.user_client, temp_id)
            raise

    async def _delete_temporary_contact(self, user_id: Optional[int]) -> None:
        await delete_temp_contact(self.user_client, user_id)

    async def _fetch_shared_group_messages(self, client_user_id: int, limit: int = 20) -> list:
        """Recent messages from groups where the client actively participates."""
        collected = []
        try:
            async for dialog in self.user_client.iter_dialogs(limit=35):
                if not dialog.is_group:
                    continue
                recent = await self.user_client.get_messages(dialog.entity, limit=20)
                # Check if the client sent any of the recent messages
                client_present = any(
                    getattr(getattr(m, "from_id", None), "user_id", None) == client_user_id
                    for m in recent
                )
                if client_present:
                    title = getattr(dialog.entity, "title", str(dialog.entity))
                    logger.info(
                        "[TELEGRAM_TASK] Found shared group '%s' with client %d",
                        title,
                        client_user_id,
                    )
                    collected.extend(recent[:limit])
        except Exception as exc:
            logger.debug("[TELEGRAM_TASK] Group scan error: %s", exc)
        return collected
