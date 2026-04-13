import logging
import asyncio
import requests
import json
from src.services.amocrm_sync import AmoCRMSync
from src.settings import settings
from src.database import Database

logger = logging.getLogger(__name__)

class MissionControl:
    def __init__(self, db=None):
        self.amo = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN,
            client_id=settings.AMOCRM_CLIENT_ID,
            client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
            redirect_url=settings.AMOCRM_REDIRECT_URL
        )
        self.amo._load_token()
        self.db = db if db else Database()
        
        self.PIPELINES = {
            "HUNTER": 10117998,
            "CLOSER": 10123314
        }
        
    async def get_active_missions(self):
        """Hunter va Closer pipelinelaridan barcha faol lidlarni yig'ish."""
        missions = []
        
        for p_name, p_id in self.PIPELINES.items():
            # Get leads for this pipeline
            url = f"{self.amo.base_url}/api/v4/leads?filter[pipeline_id]={p_id}&limit=250"
            resp = requests.get(url, headers=self.amo._get_headers())
            
            if resp.status_code == 200:
                leads = resp.json().get("_embedded", {}).get("leads", [])
                for lead in leads:
                    # Filter out closed ones
                    if lead.get("status_id") in [142, 143]:
                        continue
                        
                    mission_text = ""
                    if p_name == "HUNTER":
                        mission_text = "🎯 Lidni Closer bosqichiga olib o'ting"
                    else: # CLOSER
                        mission_text = "💰 Sotuvni yakunlang (Tugating)"
                        
                    missions.append({
                        "lead_id": lead["id"],
                        "lead_name": lead["name"],
                        "mission": mission_text,
                        "pipeline": p_name,
                        "link": f"https://{settings.AMOCRM_SUBDOMAIN}.amocrm.ru/leads/detail/{lead['id']}"
                    })
            else:
                logger.error(f"Error fetching leads for {p_name}: {resp.status_code}")
                
        return missions

    async def distribute_missions(self, managers):
        """Vazifalarni menejerlar o'rtasida bo'lib berish va bazada saqlash."""
        missions = await self.get_active_missions()
        if not missions:
            return {}

        distribution = {m['id']: [] for m in managers}
        manager_ids = [m['id'] for m in managers]
        
        if not manager_ids:
            return {}

        # Round-robin distribution
        for i, mission in enumerate(missions):
            m_id = manager_ids[i % len(manager_ids)]
            distribution[m_id].append(mission)
            
            # [ENTERPRISE] Plan-Fact uchun saqlaymiz (Hunter vs Closer KPI ajratish)
            await self.db.save_daily_plan(
                manager_id=m_id,
                lead_id=mission["lead_id"],
                lead_name=mission["lead_name"],
                mission=mission["mission"],
                source_pipeline=mission.get("pipeline", "HUNTER"),
            )
            
        return distribution

    async def get_manager_list(self):
        """Settings va DB dan faol menejerlarni olish."""
        # 1. From settings (Hard-coded/Env)
        manager_ids = list(settings.SALES_MANAGER_IDS) if hasattr(settings, "SALES_MANAGER_IDS") else []
        
        # 2. From DB state (Dynamic)
        managers_data = self.db.get_state("sales_managers", "")
        if managers_data:
            db_ids = [int(i) for i in managers_data.split(",") if i]
            for db_id in db_ids:
                if db_id not in manager_ids:
                    manager_ids.append(db_id)
        
        if manager_ids:
            # TODO: Kelajakda ismlarni ham DB dan olish mumkin
            return [{"id": mid, "name": f"Manager_{mid}"} for mid in manager_ids]
            
        return []

if __name__ == "__main__":
    # Simple test run
    async def test():
        mc = MissionControl()
        m = await mc.get_active_missions()
        print(f"Total missions found: {len(m)}")
        if m:
            print(json.dumps(m[:2], indent=2))
        
    asyncio.run(test())
