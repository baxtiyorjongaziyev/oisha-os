"""
Telegram message history retrieval and phone lookup mixin.
"""
from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from telethon import functions, types

from src.services.core.crm.enrichment.models import (
    _clip,
    _extract_role_from_history_item,
    _extract_text_from_history_item,
    maybe_await,
    normalize_phone,
)

logger = logging.getLogger("AmoCRMLeadEnrichment")


class HistoryCollectorMixin:
    """Handles dialogue discovery, phone matching, and message retrieval."""

    async def _recently_enriched(self, lead_id: int, phone: str) -> bool:
        if not self.db or self.refresh_hours <= 0:
            return False
        try:
            raw = await self.db.get_state(self._state_key(lead_id), "")
            if not raw:
                return False
            data = json.loads(raw)
            if normalize_phone(data.get("phone")) != phone:
                return False
            updated_at = data.get("updated_at")
            if not updated_at:
                return False
            dt = datetime.fromisoformat(str(updated_at))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            return age_hours < self.refresh_hours
        except Exception as exc:
            logger.debug("[AMO_ENRICH] State read skipped: %s", exc)
            return False

    async def _mark_enriched(
        self,
        lead_id: int,
        phone: str,
        telegram_user_id: Optional[int],
        message_count: int,
    ) -> None:
        if not self.db:
            return
        payload = {
            "phone": phone,
            "telegram_user_id": telegram_user_id,
            "message_count": message_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self.db.set_state(
                self._state_key(lead_id), json.dumps(payload, ensure_ascii=False)
            )
        except Exception as exc:
            logger.debug("[AMO_ENRICH] State write skipped: %s", exc)

    @staticmethod
    def _state_key(lead_id: int) -> str:
        return f"amocrm_lead_enrichment:{lead_id}"

    async def _find_telegram_profile(self, phone: str) -> Dict[str, Any]:
        profile: Dict[str, Any] = {}

        if self.db:
            try:
                db_user = await self.db.get_user_by_phone(phone)
                if db_user:
                    profile.update(db_user)
                    profile["source"] = "db"
            except Exception as exc:
                logger.debug("[AMO_ENRICH] DB phone lookup skipped: %s", exc)

        if self._profile_user_id(profile) or not self.user_client:
            return profile

        user = await self._lookup_userbot_by_phone(phone)
        if not user:
            return profile

        profile.update(user)
        profile["source"] = "userbot"
        if self.db:
            try:
                await self.db.upsert_user(
                    user_id=int(user["user_id"]),
                    first_name=user.get("first_name") or "Telegram user",
                    username=user.get("username"),
                    phone=phone,
                    last_name=user.get("last_name"),
                )
            except Exception as exc:
                logger.debug("[AMO_ENRICH] DB upsert skipped: %s", exc)
        return profile

    async def _lookup_userbot_by_phone(self, phone: str) -> Dict[str, Any]:
        if functions is None or types is None:
            return {}

        try:
            is_authorized = True
            if hasattr(self.user_client, "is_user_authorized"):
                is_authorized = bool(
                    await maybe_await(self.user_client.is_user_authorized())
                )
            if not is_authorized:
                return {}

            clean_phone = phone.replace("+", "")
            contact = types.InputPhoneContact(
                client_id=random.randrange(-(2**63), 2**63),
                phone=clean_phone,
                first_name="Oisha Lookup",
                last_name="",
            )
            result = await self.user_client(
                functions.contacts.ImportContactsRequest(contacts=[contact])
            )
            users = getattr(result, "users", None) or []
            if not users:
                return {}
            imported = getattr(result, "imported", None) or []

            user = users[0]
            user_id = getattr(user, "id", None)
            data = {
                "user_id": int(user_id) if user_id is not None else None,
                "username": getattr(user, "username", None),
                "first_name": getattr(user, "first_name", None),
                "last_name": getattr(user, "last_name", None),
                "phone": phone,
            }

            if user_id is not None and imported:
                try:
                    await self.user_client(
                        functions.contacts.DeleteContactsRequest(id=[int(user_id)])
                    )
                except Exception:
                    logger.debug("[AMO_ENRICH] Failed to delete imported contact for user %s", user_id, exc_info=True)
            return {k: v for k, v in data.items() if v is not None}
        except Exception as exc:
            logger.warning("[AMO_ENRICH] Userbot phone lookup failed: %s", exc)
            return {}

    async def _collect_messages(
        self, telegram_user_id: Optional[int]
    ) -> List[Dict[str, str]]:
        if not telegram_user_id:
            return []

        messages: List[Dict[str, str]] = []
        if self.db:
            try:
                history = await self.db.get_recent_messages(
                    int(telegram_user_id), limit=self.message_limit
                )
                for item in history or []:
                    if not isinstance(item, dict):
                        continue
                    text = _extract_text_from_history_item(item)
                    if not text:
                        continue
                    messages.append(
                        {
                            "role": _extract_role_from_history_item(item),
                            "text": _clip(text, 800),
                            "created_at": str(item.get("created_at") or ""),
                        }
                    )
            except Exception as exc:
                logger.debug("[AMO_ENRICH] DB history skipped: %s", exc)

        if messages or not self.user_client:
            return messages[-self.message_limit :]

        try:
            async for msg in self.user_client.iter_messages(
                int(telegram_user_id), limit=self.message_limit
            ):
                text = str(getattr(msg, "text", "") or "").strip()
                if not text:
                    continue
                messages.append(
                    {
                        "role": "Oisha" if getattr(msg, "out", False) else "Mijoz",
                        "text": _clip(text, 800),
                        "created_at": str(getattr(msg, "date", "") or ""),
                    }
                )
        except Exception as exc:
            logger.debug("[AMO_ENRICH] Userbot history skipped: %s", exc)

        return list(reversed(messages))[-self.message_limit :]


    @staticmethod
    def _profile_user_id(profile: Dict[str, Any]) -> Optional[int]:
        value = profile.get("user_id") or profile.get("id")
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _display_name(profile: Dict[str, Any]) -> str:
        return " ".join(
            str(part).strip()
            for part in (
                profile.get("first_name") or profile.get("contact_name"),
                profile.get("last_name"),
            )
            if part
        ).strip()
