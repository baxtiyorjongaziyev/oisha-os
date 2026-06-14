import asyncio
import json
import logging

import requests

from src.database import Database
from .amocrm_sync import AmoCRMSync
from src.settings import settings
from src.agents.negotiation_engine import NegotiationEngine
from src.services.core.amocrm_pipeline_config import (
    ACTIVE_PIPELINE_IDS,
    FARMER_PIPELINE_ID as CONFIG_FARMER_PIPELINE_ID,
    LEGACY_CLOSER_PIPELINE_ID,
    REACTIVATION_DAILY_LIMIT,
    REACTIVATION_PIPELINE_ID,
    SALES_PIPELINE_ID,
)

logger = logging.getLogger(__name__)


class MissionControlFetchError(RuntimeError):
    """AmoCRM holati noaniq bo'lib qolganida ko'tariladi."""


class MissionControl:
    # Pipeline Constants
    HUNTER_PIPELINE_ID = SALES_PIPELINE_ID
    CLOSER_PIPELINE_ID = LEGACY_CLOSER_PIPELINE_ID
    FARMER_PIPELINE_ID = CONFIG_FARMER_PIPELINE_ID

    def __init__(self, db=None):
        self.amo = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN,
            client_id=settings.AMOCRM_CLIENT_ID,
            client_secret=(
                settings.AMOCRM_CLIENT_SECRET.get_secret_value()
                if settings.AMOCRM_CLIENT_SECRET
                else None
            ),
            redirect_url=settings.AMOCRM_REDIRECT_URL,
        )
        self.amo._load_token()
        self.db = db if db else Database()
        self.last_fetch_errors = []

    def get_pipeline_role(self, pipeline_id: int) -> str:
        """Pipeline ID ga qarab rolni aniqlash."""
        if pipeline_id == self.HUNTER_PIPELINE_ID:
            return "SALES"
        if pipeline_id == self.CLOSER_PIPELINE_ID:
            return "SALES_LEGACY"
        if pipeline_id == self.FARMER_PIPELINE_ID:
            return "FARMER"
        return "SALES"  # Default

    def _fetch_pipeline_leads_sync(self, pipeline_name, pipeline_id):
        """Bitta pipeline uchun leadlarni olib kelish, kerak bo'lsa tokenni yangilash."""
        url = f"{self.amo.base_url}/api/v4/leads?filter[pipeline_id]={pipeline_id}&limit=250"
        response = requests.get(url, headers=self.amo._get_headers(), timeout=30)

        if response.status_code == 401:
            logger.warning(
                f"[MISSION CONTROL] {pipeline_name} returned 401, attempting token refresh."
            )
            if self.amo.refresh_token():
                response = requests.get(
                    url, headers=self.amo._get_headers(), timeout=30
                )

        if response.status_code != 200:
            details = response.text.strip()
            if len(details) > 200:
                details = details[:200]
            error = f"{pipeline_name}: HTTP {response.status_code}" + (
                f" - {details}" if details else ""
            )
            logger.error(
                f"[MISSION CONTROL] Error fetching leads for {pipeline_name}: {error}"
            )
            return [], error

        leads = response.json().get("_embedded", {}).get("leads", [])
        return leads, None

    async def get_active_missions(self):
        """Faol voronkalardan (ACTIVE_PIPELINE_IDS) barcha faol lidlarni yig'ish."""
        missions = []
        self.last_fetch_errors = []

        try:
            for p_id in ACTIVE_PIPELINE_IDS:
                pipeline_label = f"pipeline_{p_id}"

                leads, error = await asyncio.to_thread(
                    self._fetch_pipeline_leads_sync,
                    pipeline_label,
                    p_id,
                )
                if error:
                    self.last_fetch_errors.append(error)
                    continue

                # Reactivation pipeline — kunlik limitni qo'llash
                if p_id == REACTIVATION_PIPELINE_ID:
                    leads = sorted(leads, key=lambda l: l.get("updated_at", 0))[:REACTIVATION_DAILY_LIMIT]

                for lead in leads:
                    if lead.get("status_id") in [142, 143]:
                        continue

                    lead_id = lead["id"]
                    p_name = pipeline_label

                    # --- SURGICAL MISSION LOGIC ---
                    surgical_mission = None

                    # 1. AmoCRM-dan mavjud vazifalarni tekshirish
                    try:
                        tasks_url = f"{self.amo.base_url}/api/v4/tasks?filter[entity_id]={lead_id}&filter[entity_type]=leads&filter[is_completed]=0"
                        t_res = requests.get(
                            tasks_url, headers=self.amo._get_headers(), timeout=10
                        )
                        if t_res.status_code == 200:
                            tasks = t_res.json().get("_embedded", {}).get("tasks", [])
                            if tasks:
                                surgical_mission = tasks[0].get("text")
                    except Exception as te:
                        logger.warning(
                            f"[MISSION CONTROL] Task fetch error for {lead_id}: {te}"
                        )

                    # 2. Agar vazifa bo'lmasa, Chat Summary va AI orqali generatsiya qilish
                    if not surgical_mission:
                        try:
                            role = self.get_pipeline_role(p_id)

                            phone = self.amo.get_lead_phone(lead_id)
                            user_id = None
                            summary = None

                            if phone:
                                user_info = await self.db.get_user_by_phone(phone)
                                if user_info:
                                    user_id = user_info.get("user_id")
                                    summary = await self.db.get_chat_summary(user_id)

                            assessment = NegotiationEngine.assess(
                                message=summary or "Yangi lead", crm_status=p_name
                            )
                            surgical_mission = (
                                await NegotiationEngine.generate_surgical_mission(
                                    assessment=assessment,
                                    summary=summary,
                                    pipeline_name=p_name,
                                    role=role,
                                )
                            )
                        except Exception as ae:
                            logger.warning(
                                f"[MISSION CONTROL] AI mission generation failed for {lead_id}: {ae}"
                            )
                            surgical_mission = (
                                f"Bitimni keyingi bosqichga o'tkazing ({p_name})"
                            )

                    missions.append(
                        {
                            "lead_id": lead_id,
                            "lead_name": lead["name"],
                            "mission": surgical_mission,
                            "pipeline": p_name,
                            "pipeline_id": p_id,
                            "role": self.get_pipeline_role(p_id),
                            "link": f"https://{settings.AMOCRM_SUBDOMAIN}.amocrm.ru/leads/detail/{lead_id}",
                        }
                    )
        except Exception as e:
            logger.error(f"[MISSION CONTROL] Universal fetch error: {e}")
            self.last_fetch_errors.append(str(e))

        if not missions and self.last_fetch_errors:
            raise MissionControlFetchError(
                "AmoCRM pipeline fetch failed; pipeline holati noaniq. "
                + " | ".join(self.last_fetch_errors)
            )

        return missions

    async def distribute_missions(self, managers):
        """Vazifalarni menejerlar o'rtasida bo'lib berish va bazada saqlash."""
        missions = await self.get_active_missions()
        if not missions:
            return {}

        distribution = {m["id"]: [] for m in managers}
        manager_ids = [m["id"] for m in managers]

        if not manager_ids:
            return {}

        for index, mission in enumerate(missions):
            manager_id = manager_ids[index % len(manager_ids)]
            distribution[manager_id].append(mission)

            await self.db.save_daily_plan(
                manager_id=manager_id,
                lead_id=mission["lead_id"],
                lead_name=mission["lead_name"],
                mission=mission["mission"],
                source_pipeline=mission.get("role", "HUNTER"),
            )

        return distribution

    async def get_manager_list(self):
        """Settings va DB dan faol menejerlarni olish."""
        manager_ids = (
            list(settings.SALES_MANAGER_IDS)
            if hasattr(settings, "SALES_MANAGER_IDS")
            else []
        )

        managers_data = self.db.get_state("sales_managers", "")
        if managers_data:
            db_ids = [int(i) for i in managers_data.split(",") if i]
            for db_id in db_ids:
                if db_id not in manager_ids:
                    manager_ids.append(db_id)

        if manager_ids:
            return [{"id": mid, "name": f"Manager_{mid}"} for mid in manager_ids]

        return []


if __name__ == "__main__":

    async def test():
        mission_control = MissionControl()
        missions = await mission_control.get_active_missions()
        print(f"Total missions found: {len(missions)}")
        if missions:
            print(json.dumps(missions[:2], indent=2))

    asyncio.run(test())
