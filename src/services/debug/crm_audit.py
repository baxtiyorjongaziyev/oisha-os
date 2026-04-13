import asyncio
import logging
import time
import requests
from datetime import datetime, timezone, timedelta
from src.services.amocrm_sync import AmoCRMSync
from src.settings import settings

logger = logging.getLogger(__name__)

class AmoCRMAudit:
    def __init__(self):
        self.amo = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN,
            client_id=settings.AMOCRM_CLIENT_ID,
            client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
            redirect_url=settings.AMOCRM_REDIRECT_URL
        )

    async def run_full_audit(self):
        self.amo._load_token()
        if not self.amo.access_token:
            return {"error": "AmoCRM token topilmadi yoki muddati o'tgan."}
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "pipelines": {},
            "stagnation": {"24h": 0, "48h": 0, "7d+": 0},
            "tasks": {"no_tasks": [], "overdue": []},
            "unsorted": 0,
            "summary": ""
        }
        
        try:
            # 1. Pipelines info
            pipe_resp = requests.get(f"{self.amo.base_url}/api/v4/leads/pipelines", headers=self.amo._get_headers())
            pipelines_data = pipe_resp.json().get("_embedded", {}).get("pipelines", [])
            status_names = {}
            for p in pipelines_data:
                for s in p.get("_embedded", {}).get("statuses", []):
                    status_names[s["id"]] = f"{p['name']} -> {s['name']}"

            # 2. Extract Leads (Fetch up to 200 leads to get a good sample)
            all_leads = []
            for page in [1, 2]:
                url = f"{self.amo.base_url}/api/v4/leads?limit=100&page={page}"
                resp = requests.get(url, headers=self.amo._get_headers())
                if resp.status_code == 200:
                    page_leads = resp.json().get("_embedded", {}).get("leads", [])
                    all_leads.extend(page_leads)
                else: break

            if not all_leads:
                return {"error": "Lidlar topilmadi."}
            
            # Tasks mapping
            all_tasks = await self.amo.get_tasks()
            task_entity_ids = {t.get("entity_id") for t in all_tasks if t.get("entity_type") == "leads"}
            
            now_ts = time.time()
            for lead in all_leads:
                lid = lead["id"]
                s_id = lead["status_id"]
                results["pipelines"][s_id] = results["pipelines"].get(s_id, 0) + 1
                
                updated_at = lead["updated_at"]
                diff = now_ts - updated_at
                if diff > 7 * 24 * 3600: results["stagnation"]["7d+"] += 1
                elif diff > 48 * 3600: results["stagnation"]["48h"] += 1
                elif diff > 24 * 3600: results["stagnation"]["24h"] += 1
                
                if lid not in task_entity_ids:
                    results["tasks"]["no_tasks"].append(lid)
                else:
                    lead_tasks = [t for t in all_tasks if t.get("entity_id") == lid]
                    if any(t.get("complete_till", 0) < now_ts for t in lead_tasks):
                        results["tasks"]["overdue"].append(lid)

            # 3. Unsorted
            un_resp = requests.get(f"{self.amo.base_url}/api/v4/leads/unsorted", headers=self.amo._get_headers())
            if un_resp.status_code == 200:
                results["unsorted"] = len(un_resp.json().get("_embedded", {}).get("unsorted", []))

            # Summary generation
            lines = [f"📊 **AmoCRM Audit Natijalari ({len(all_leads)} lid tahlil qilindi):**"]
            lines.append(f"- ⚠️ **Vazifasi yo'q (unudilgan) lidlar: {len(results['tasks']['no_tasks'])}**")
            lines.append(f"- ⏰ Muddati o'tgan vazifalar: {len(results['tasks']['overdue'])}")
            lines.append(f"- 📥 Saralanmagan (Unsorted) xabarlar: {results['unsorted']}")
            lines.append(f"- 🧊 7 kundan beri harakatsiz: {results['stagnation']['7d+']}")
            
            # Health Score Formula: 
            # penalty: -5 for each overdue, -2 for each no_task (from the sample of leads)
            # but more balanced: (Leads_with_valid_task / total_leads) * 100
            total = len(all_leads)
            problematic = len(set(results["tasks"]["no_tasks"]) | set(results["tasks"]["overdue"]))
            health = int(max(0, 100 * (1 - (problematic / total)))) if total > 0 else 100
            results["health_score"] = health
            
            lines.append(f"\n🎯 **CRM Tozalik Ko'rsatkichi: {health}%**")
            lines.append("\n**Statuslar bo'yicha taqsimot:**")
            for s_id, count in results["pipelines"].items():
                name = status_names.get(s_id, f"ID: {s_id}")
                lines.append(f"  - {name}: {count}")
            
            results["summary"] = "\n".join(lines)
            return results
            
        except Exception as e:
            logger.error(f"Audit error: {e}")
            return {"error": str(e)}

if __name__ == "__main__":
    audit = AmoCRMAudit()
    asyncio.run(audit.run_full_audit())
