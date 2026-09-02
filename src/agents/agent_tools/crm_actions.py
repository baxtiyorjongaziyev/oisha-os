import logging
import asyncio
from datetime import datetime
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)

from src.agents.agent_tools.crm_lead_qualify import CrmLeadQualifyMixin


class CrmActionsMixin(CrmLeadQualifyMixin):
    async def _save_lead_info(
        self,
        user_id: int,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        business_type: Optional[str] = None,
        region: Optional[str] = None,
        brand_name: Optional[str] = None,
        service_type: Optional[str] = None,
        deadline: Optional[str] = None,
        lead_quality: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mijoz ma'lumotlarini SQLite va Google Sheets ga saqlash."""
        import asyncio

        saved_fields = []

        # SQLite
        try:
            kwargs = {}
            if business_type:
                kwargs["business_type"] = business_type
            if region:
                kwargs["region"] = region
            if brand_name:
                kwargs["brand_name"] = brand_name
            if service_type:
                kwargs["service_type"] = service_type
            if deadline:
                kwargs["deadline"] = deadline

            await asyncio.to_thread(
                self.db.upsert_user, user_id, name or "Unknown", None, phone, **kwargs
            )
            saved_fields.append("SQLite DB")
        except Exception as e:
            logger.error(f"[TOOL] save_lead_info SQLite xato: {e}")

        # Google Sheets
        try:
            await asyncio.to_thread(
                self.gsheet.sync_user,
                user_id,
                name or "Unknown",
                None,
                phone=phone,
                business_type=business_type,
                region=region,
                brand_name=brand_name,
                service_type=service_type,
                deadline=deadline,
            )
            saved_fields.append("Google Sheets")
        except Exception as e:
            logger.error(f"[TOOL] save_lead_info GSheets xato: {e}")

        # AmoCRM
        try:
            if phone:
                await asyncio.to_thread(
                    self.amocrm.create_lead,
                    name or f"User {user_id}",
                    phone,
                    price=0,
                    note=f"Biznes: {business_type}, Hudud: {region}",
                )
                saved_fields.append("AmoCRM")
        except Exception as e:
            logger.error(f"[TOOL] save_lead_info AmoCRM xato: {e}")

        # Agent action log
        await self._log_action(
            user_id,
            "save_lead_info",
            {
                "name": name,
                "phone": phone,
                "business_type": business_type,
                "lead_quality": lead_quality,
            },
            success=True,
        )

        return {
            "success": True,
            "message": f"Ma'lumotlar saqlandi: {', '.join(saved_fields)}",
            "saved": {
                "name": name,
                "phone": phone,
                "business_type": business_type,
                "region": region,
                "lead_quality": lead_quality,
            },
        }

    async def _get_crm_status_tool(self, user_id: int) -> Dict[str, Any]:
        """AmoCRM dan lead holatini olib kelish."""
        user_info = await self._db_call("get_user_info", user_id)
        phone = user_info.get("phone") if user_info else None

        if not phone:
            return {
                "success": False,
                "error": "Foydalanuvchi telefoni topilmadi. Avval raqamni saqlang.",
            }

        try:
            from src.services.core.crm.crm_service import CRMService

            crm = CRMService()
            status = await crm.get_user_context(phone)
            return {"success": True, "status": status}
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {"success": False, "error": str(e)}

    async def _update_lead_status(
        self, user_id: int, status_name: str
    ) -> Dict[str, Any]:
        """AmoCRM da bitim statusini o'zgartirish."""
        import asyncio

        user_info = await self._db_call("get_user_info", user_id)
        phone = user_info.get("phone") if user_info else None

        if not phone:
            return {"success": False, "error": "Raqam yo'q - status o'zgartirilmadi."}

        # Hunter Pipeline (ID: 10117998)
        hunter_id = 10117998
        status_map = {
            "Initial Contact": {
                "id": 80178218,
                "pid": hunter_id,
                "name": "Malakalash kutilmoqda",
            },
            "Negotiation": {
                "id": 80178222,
                "pid": hunter_id,
                "name": "Muloqot boshlandi",
            },
            "Qualified": {
                "id": 80178222,
                "pid": hunter_id,
                "name": "Muloqot boshlandi",
            },
            "Interested": {
                "id": 80178226,
                "pid": hunter_id,
                "name": "Qiziqish tasdiqlandi",
            },
            "Meeting Scheduled": {
                "id": 80178230,
                "pid": hunter_id,
                "name": "Strategik sessiya",
            },
            "Conversation Over": {
                "id": 80215318,
                "pid": 10123314,
            },  # Closer pipeline: Konsultatsiya o'tdi
            "Closed Lost": {"id": 143, "pid": hunter_id},
        }

        status_info = status_map.get(status_name)
        if not status_info:
            return {"success": False, "error": f"Unknown status: {status_name}"}

        try:
            lead = await asyncio.to_thread(self.amocrm.get_lead_by_phone, phone)
            if lead:
                lead_id = lead.get("id")
                success = await self.amocrm.update_lead_status(
                    lead_id, status_info["id"], status_info["pid"]
                )
                if success:
                    # Also add a note about the status change
                    await self.amocrm.add_lead_note(
                        lead_id, f"AI statusni o'zgartirdi: {status_name}"
                    )
                    await self._log_action(
                        user_id,
                        "update_lead_status",
                        {"status": status_name},
                        success=True,
                    )
                    return {
                        "success": True,
                        "message": f"Status o'zgartirildi: {status_name}",
                    }
            return {"success": False, "error": "Lead topilmadi."}
        except Exception as e:
            logger.error(f"[TOOL ERROR] update_lead_status: {e}")
            return {"success": False, "error": str(e)}

    async def _create_followup_task(
        self,
        title: str,
        details: Optional[str] = None,
        user_id: Optional[int] = None,
        lead_id: Optional[int] = None,
        due_at: Optional[str] = None,
        due_in_hours: Optional[int] = None,
    ) -> Dict[str, Any]:
        """AmoCRM ichida lead uchun follow-up vazifa yaratish.

        Working hours: 10:00-17:00 (Toshkent), Dushanba-Shanba.
        Vazifalar ish vaqti ichida tarqatiladi.
        """
        from src.utils.task_scheduler import task_deadline

        lead_context = await self._resolve_lead_context(
            user_id=user_id, lead_id=lead_id
        )
        resolved_lead_id = lead_context.get("lead_id")
        if not resolved_lead_id:
            return {
                "success": False,
                "error": "Lead topilmadi - follow-up task yaratilmadi.",
            }

        deadline_hours = max(1, due_in_hours or 24)
        if due_at:
            try:
                due_dt = datetime.datetime.fromisoformat(due_at)
            except ValueError:
                return {"success": False, "error": f"Noto'g'ri due_at format: {due_at}"}
        else:
            # Ish vaqtini hisobga olgan holda deadline
            complete_till_ts = task_deadline(due_in_hours=deadline_hours)
            due_dt = datetime.datetime.fromtimestamp(
                complete_till_ts, tz=datetime.timezone.utc
            )

        complete_till = int(due_dt.timestamp())
        task_text = title.strip()
        if details:
            task_text = f"{task_text}. {details.strip()}"

        try:
            created = await self.amocrm.create_task(
                resolved_lead_id, task_text[:500], complete_till
            )
            if not created:
                return {"success": False, "error": "AmoCRM follow-up task yaratilmadi."}

            await self._log_action(
                user_id,
                "create_followup_task",
                {
                    "lead_id": resolved_lead_id,
                    "title": title,
                    "details": details,
                    "due_at": due_dt.isoformat(),
                },
                success=True,
            )
            return {
                "success": True,
                "lead_id": resolved_lead_id,
                "message": f"Follow-up task yaratildi: {title}",
                "due_at": due_dt.isoformat(),
            }
        except Exception as e:
            logger.error(f"[TOOL ERROR] create_followup_task: {e}")
            return {"success": False, "error": str(e)}

    async def _add_lead_note(
        self,
        note: str,
        user_id: Optional[int] = None,
        lead_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """AmoCRM lead kartasiga izoh qo'shish."""
        lead_context = await self._resolve_lead_context(
            user_id=user_id, lead_id=lead_id
        )
        resolved_lead_id = lead_context.get("lead_id")
        if not resolved_lead_id:
            return {"success": False, "error": "Lead topilmadi - note yozilmadi."}

        try:
            added = await asyncio.to_thread(
                self.amocrm.add_lead_note, resolved_lead_id, note[:1500]
            )
            if not added:
                return {"success": False, "error": "AmoCRM lead note yozilmadi."}

            await self._log_action(
                user_id,
                "add_lead_note",
                {
                    "lead_id": resolved_lead_id,
                    "note": note,
                },
                success=True,
            )
            return {
                "success": True,
                "lead_id": resolved_lead_id,
                "message": "Lead note yozildi.",
            }
        except Exception as e:
            logger.error(f"[TOOL ERROR] add_lead_note: {e}")
            return {"success": False, "error": str(e)}
