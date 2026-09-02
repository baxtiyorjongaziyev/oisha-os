import structlog
from telethon import functions, types
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()

class AdminLookupMixin:
    async def _perform_global_lookup(self, phone: str):
        """Global qidiruvni amalga oshirish."""
        return await self._perform_global_lookup_userbot(phone)

    async def _perform_global_lookup_userbot(self, phone: str):
        """Userbot orqali Telegramdan qidirish — contacts.resolvePhone (toza, side-effect yo'q)."""
        from telethon.tl.functions.contacts import ResolvePhoneRequest

        clean_phone = "+" + "".join(c for c in phone if c.isdigit())
        digits = clean_phone.lstrip("+")
        if len(digits) == 9:
            clean_phone = "+998" + digits
        elif len(digits) == 11 and digits.startswith("8"):
            clean_phone = "+7" + digits[1:]

        try:
            result = await self.user_client(ResolvePhoneRequest(phone=clean_phone))
            if result.users:
                user = result.users[0]
                return {
                    "user_id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                }
            return None
        except Exception as e:
            logger.warning("[GLOBAL SEARCH] resolvePhone failed (%s), falling back to importContacts", type(e).__name__)
            return await self._perform_global_lookup_import_fallback(clean_phone)

    async def _perform_global_lookup_import_fallback(self, clean_phone: str):
        """Fallback: contacts.importContacts (eski metod, agar resolvePhone ishlamasa)."""
        import random

        try:
            contact = types.InputPhoneContact(
                client_id=random.randrange(-(2**63), 2**63),
                phone=clean_phone.lstrip("+"),
                first_name="Lookup",
                last_name="",
            )
            result = await self.user_client(
                functions.contacts.ImportContactsRequest(contacts=[contact])
            )
            if result.users:
                user = result.users[0]
                user_data = {
                    "user_id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                }
                newly_added_ids = {imp.user_id for imp in (result.imported or [])}
                if user.id in newly_added_ids:
                    await self.user_client(
                        functions.contacts.DeleteContactsRequest(id=[user.id])
                    )
                return user_data
            return None
        except Exception as e:
            logger.error("[GLOBAL SEARCH FALLBACK ERROR] %s", e)
            return None
