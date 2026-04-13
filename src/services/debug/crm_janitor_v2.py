import asyncio
import logging
import json
import time
from datetime import datetime, timedelta, timezone
from src.services.amocrm_sync import AmoCRMSync
from src.settings import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CRMJanitorV2:
    def __init__(self, dry_run=True):
        self.amo = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN,
            client_id=settings.AMOCRM_CLIENT_ID,
            client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
            redirect_url=settings.AMOCRM_REDIRECT_URL
        )
        self.amo._load_token()
        self.dry_run = dry_run
        self.report = {
            "duplicates_found": 0,
            "stale_leads_found": 0,
            "merges_proposed": [],
            "tag_updates_proposed": []
        }

    async def run_cleanup(self):
        logger.info(f"🧹 CRM Janitor V2 ishga tushdi (Dry Run: {self.dry_run})")
        
        # 1. Duplicate Detection (Contacts)
        await self.find_duplicate_contacts()
        
        # 2. Stagnation Cleanup (Leads)
        await self.find_stale_leads()
        
        # 3. Final Report
        self.display_report()

    async def find_duplicate_contacts(self):
        logger.info("🔍 Kontaktlardan dublikatlarni qidirish...")
        # Get last 250 contacts for auditing
        import requests
        url = f"{self.amo.base_url}/api/v4/contacts?limit=250"
        resp = requests.get(url, headers=self.amo._get_headers())
        
        if resp.status_code != 200:
            logger.error(f"Failed to fetch contacts: {resp.status_code}")
            return

        contacts = resp.json().get("_embedded", {}).get("contacts", [])
        phone_map = {} # phone -> list of contact objects

        for contact in contacts:
            # Extract phone from custom fields
            phone = None
            cfs = contact.get("custom_fields_values") or []
            for cf in cfs:
                if cf.get("field_code") == "PHONE":
                    phone = cf.get("values", [{}])[0].get("value")
                    break
            
            if phone:
                # Standardize phone for comparison
                clean_phone = "".join(filter(str.isdigit, str(phone)))
                if clean_phone:
                    if clean_phone not in phone_map:
                        phone_map[clean_phone] = []
                    phone_map[clean_phone].append(contact)

        # Identify duplicates
        for phone, matched_contacts in phone_map.items():
            if len(matched_contacts) > 1:
                self.report["duplicates_found"] += 1
                names = [c["name"] for c in matched_contacts]
                ids = [c["id"] for c in matched_contacts]
                logger.warning(f"DUPLICATE FOUND: {phone} -> {names} (IDs: {ids})")
                self.report["merges_proposed"].append({
                    "phone": phone,
                    "ids": ids,
                    "primary": ids[0] # Simplistic choice
                })

    async def find_stale_leads(self):
        logger.info("🔍 'Muzlab qolgan' (stagnant) lidlarni qidirish...")
        # Get open leads
        leads = await self.amo.get_leads()
        now = time.time()
        stale_threshold = 14 * 24 * 3600 # 14 days

        for lead in leads:
            updated_at = lead.get("updated_at", 0)
            status_id = lead.get("status_id")
            
            # Skip Won/Lost
            if status_id in [142, 143]: continue

            if (now - updated_at) > stale_threshold:
                self.report["stale_leads_found"] += 1
                logger.warning(f"STALE LEAD identified: {lead['id']} (Last update: {datetime.fromtimestamp(updated_at)})")
                self.report["tag_updates_proposed"].append({
                    "id": lead["id"],
                    "tag": "STALE"
                })
                
                if not self.dry_run:
                    await self.amo.add_lead_tag(lead["id"], "STALE")

    def display_report(self):
        print("\n" + "="*40)
        print("📊 CRM CLEANUP HISOBOTI (JANITOR V2)")
        print("="*40)
        print(f"👥 Topilgan dublikatlar: {self.report['duplicates_found']}")
        print(f"❄️ 'Muzlagan' lidlar: {self.report['stale_leads_found']}")
        print(f"🔄 Dry Run rejimida: {self.dry_run}")
        print("="*40)
        if self.dry_run:
            print("💡 Maslahat: Haqiqiy tozalash uchun dry_run=False qilib ishlating.")
        print("="*40 + "\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CRM Janitor V2 - AmoCRM Optimization Tool")
    parser.add_argument("--fix", action="store_true", help="Apply changes (default is Dry Run)")
    args = parser.parse_args()

    janitor = CRMJanitorV2(dry_run=not args.fix)
    asyncio.run(janitor.run_cleanup())
