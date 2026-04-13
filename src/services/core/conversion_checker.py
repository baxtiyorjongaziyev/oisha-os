import asyncio
import logging
from typing import List, Dict, Any
from src.services.amocrm_sync import AmoCRMSync
from src.services.airtable_sync import AirtableSync
from src.settings import settings

logger = logging.getLogger(__name__)

class ConversionChecker:
    """
    Oisha-OS v4.6 Conversion Checker.
    Monitors amoCRM for 'Won' leads and synchronizes them to Airtable Projects.
    """
    def __init__(self, amocrm: AmoCRMSync, airtable: AirtableSync, admin_bot=None):
        self.amocrm = amocrm
        self.airtable = airtable
        self.admin_bot = admin_bot
        self.processed_leads_file = "data/processed_conversions.txt"
        self._processed_cache = self._load_processed_cache()

    def _load_processed_cache(self) -> set:
        import os
        if os.path.exists(self.processed_leads_file):
            with open(self.processed_leads_file, "r") as f:
                return set(line.strip() for line in f if line.strip())
        return set()

    def _save_to_cache(self, lead_id: str):
        self._processed_cache.add(str(lead_id))
        with open(self.processed_leads_file, "a") as f:
            f.write(f"{lead_id}\n")

    async def check_conversions(self):
        """
        Polls amoCRM for 'Won' leads (Status 142).
        """
        logger.info("👸 [CONVERSION] Checking for 'Won' leads in amoCRM...")
        # 142 is typical for 'Success/Won' in amoCRM. 
        # In some accounts it might be different, but 142 is the default for 'Closed Won'.
        won_leads = await self.amocrm.get_leads(status_id=142)
        
        for lead in won_leads:
            lead_id = str(lead.get("id"))
            if lead_id in self._processed_cache:
                continue

            logger.info(f"👸 [CONVERSION] Found NEW conversion! Lead ID: {lead_id}")
            
            # 1. Extract Details
            lead_name = lead.get("name", "Noma'lum Loyiha")
            price = lead.get("price", 0)
            
            # Get Contact Info
            phone = self.amocrm.get_lead_phone(int(lead_id))
            
            # 2. Sync to Airtable (haqiqiy maydon nomlari)
            airtable_fields = {
                "Loyihani nomi?": lead_name,
                "Client Phone": phone or "N/A",
                "Jami loyiha narxi (UZS)": price,
                "Source": "amoCRM Conversion",
                "Loyiha bosqichi": "Boshlanmoqda",
                "Start sana": lead.get("closed_at_date") or ""
            }
            
            result = self.airtable.create_record(airtable_fields)
            
            if result:
                logger.info(f"👸 [CONVERSION] Successfully created Airtable project for {lead_name}")
                self._save_to_cache(lead_id)
                
                # 3. Notify Team
                if self.admin_bot:
                    msg = (
                        f"🎊 **YANGI LOYIHA BOSHLANDI!** 🎊\n"
                        f"──────────────────────\n"
                        f"🚀 **Loyiha:** {lead_name}\n"
                        f"💰 **Budjet:** {price:,} so'm\n"
                        f"📞 **Mijoz:** {phone or 'Raqam yoq'}\n"
                        f"──────────────────────\n"
                        f"✅ Airtable-ga ('Loyihalar') muvaffaqiyatli qo'shildi.\n"
                        f"CC: @Inomjon (Project Manager)"
                    )
                    await self.admin_bot.notify_team(msg)

    async def run_forever(self, interval: int = 3600):
        """
        Background loop for the conversion checker.
        """
        while True:
            try:
                await self.check_conversions()
            except Exception as e:
                logger.error(f"👸 [CONVERSION ERROR] {e}")
            await asyncio.sleep(interval)

if __name__ == "__main__":
    # Integration test snippet
    pass
