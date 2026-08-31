"""
CRM Lead qualification and search actions for Agent Tools.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CrmLeadQualifyMixin:
    """Lead qualification scoring and lead search actions."""

    async def _qualify_lead(
        self,
        user_id: int,
        source: Optional[str] = None,
        service: Optional[str] = None,
        temperature: Optional[str] = None,
        need: Optional[str] = None,
        budget_range: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """AmoCRM maydonlarini va teglarini yangilash."""
        import asyncio

        user_info = await self._db_call("get_user_info", user_id)
        phone = user_info.get("phone") if user_info else None

        if not phone:
            return {"success": False, "error": "Raqam yo'q - ma'lumotlar yangilanmadi."}

        fields_to_update = {}
        # Mapping Enums
        field_maps = {
            "source": {
                1034663: {
                    "Telegram": 965705,
                    "Instagram": 965707,
                    "Facebook": 965709,
                    "Sayt": 965703,
                }
            },
            "service": {
                1034671: {
                    "Naming": 965739,
                    "Logo": 965741,
                    "Brandbook": 965743,
                    "Web": 965747,
                    "SMM": 965749,
                }
            },
            "temperature": {1034667: {"Sovuq": 965725, "Issiq": 965727}},
            "budget": {
                1427495: {
                    "< 500$": 1262133,
                    "500$ - 1500$": 1262135,
                    "1500$ - 3000$": 1262137,
                    "> 3000$": 1262139,
                }
            },
        }

        if source and source in field_maps["source"][1034663]:
            fields_to_update[1034663] = field_maps["source"][1034663][source]
        if service and service in field_maps["service"][1034671]:
            fields_to_update[1034671] = field_maps["service"][1034671][service]
        if temperature and temperature in field_maps["temperature"][1034667]:
            fields_to_update[1034667] = field_maps["temperature"][1034667][temperature]

        # Textarea field
        if need:
            fields_to_update[1427493] = need

        # Select field for budget
        if budget_range and budget_range in field_maps["budget"][1427495]:
            fields_to_update[1427495] = field_maps["budget"][1427495][budget_range]

        try:
            lead = await asyncio.to_thread(self.amocrm.get_lead_by_phone, phone)
            if not lead:
                return {"success": False, "error": "Lead topilmadi."}

            lead_id = lead.get("id")
            results = []

            if fields_to_update:
                f_ok = await self.amocrm.update_lead_custom_fields(
                    lead_id, fields_to_update
                )
                results.append(f"Fields: {'OK' if f_ok else 'Fail'}")

            if tag:
                t_ok = await self.amocrm.add_lead_tag(lead_id, tag)
                results.append(f"Tag: {'OK' if t_ok else 'Fail'}")
            elif temperature == "Issiq":
                await self.amocrm.add_lead_tag(lead_id, "High-Intent")
                results.append("Tag: High-Intent")

            # 3. Avtomatik Task (IDEAL PIPELINE) - Agar Issiq bo'lsa
            if temperature == "Issiq":
                import time

                deadline = int(time.time() + 3600)  # 1 soat ichida bog'lanish
                await self.amocrm.create_task(
                    lead_id, f"ISSUR: {phone} - Tezkor aloqa! (AI malakaladi)", deadline
                )
                # Shuningdek jamoaga xabar yuborish
                await self._assign_task_to_human(
                    1774538344630,
                    f"Issiq lid! Telefon: {phone}. Ehtiyoj: {need or 'aniqlanmoqda'}",
                    "High",
                )
                results.append("Task: Created")

            # Always add Oisha-AI tag if qualified
            await self.amocrm.add_lead_tag(lead_id, "Oisha-AI")

            return {"success": True, "message": " | ".join(results)}
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {"success": False, "error": str(e)}

    async def _search_crm_leads(
        self,
        query: str = "",
        limit: int = 5,
    ) -> Dict[str, Any]:
        """AmoCRM da lidlarni qidirish va qaytarish."""
        try:
            fetch_fn = (
                self.amocrm.get_leads_detailed
                if hasattr(self.amocrm, "get_leads_detailed")
                else self.amocrm.get_leads
            )
            leads = await asyncio.to_thread(fetch_fn, limit=min(limit * 4, 50))
            if query:
                q = query.lower()
                leads = [
                    l for l in leads
                    if q in str(l.get("name", "")).lower()
                    or q in str(l.get("price", ""))
                ]
            leads = leads[:limit]
            results = [
                {
                    "id": l.get("id"),
                    "name": l.get("name"),
                    "price": l.get("price", 0),
                    "status_id": l.get("status_id"),
                    "pipeline_id": l.get("pipeline_id"),
                    "created_at": l.get("created_at"),
                }
                for l in leads
            ]
            return {"success": True, "leads": results, "count": len(results)}
        except Exception as e:
            logger.error(f"[TOOL] search_crm_leads error: {e}")
            return {"success": False, "error": str(e)}
