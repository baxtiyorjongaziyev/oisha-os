import logging
import time
import asyncio
from datetime import datetime, timedelta
from src.services.core.amocrm_sync import AmoCRMSync
from src.database import Database
from src.api_server import add_activity

logger = logging.getLogger(__name__)

class CRMNightShift:
    """
    Oisha "Night Shift" v1.0.
    Automatically cleans AmoCRM duplicates, manages stagnation, and archives old leads.
    Runs during low-activity hours (e.g., 01:00 AM).
    """
    def __init__(self, amocrm: AmoCRMSync, db: Database):
        self.amocrm = amocrm
        self.db = db

    async def run_cleanup(self):
        """Execute the full night shift cycle."""
        logger.info("👸 [NIGHT SHIFT] Starting AmoCRM maintenance cycle...")
        add_activity("Night Shift", "CRM tozalash va audit boshlandi...", "thinking")
        
        try:
            # 1. Deduplicate Contacts
            add_activity("CRM Audit", "Dublikatlarni qidirish boshlandi...", "info")
            dupes = await self.deduplicate_contacts()
            add_activity("CRM Audit", f"{dupes} ta dublikat aniqlandi va belgilandi.", "success")
            
            # 2. Flag Stagnated Leads (>7 days)
            add_activity("CRM Audit", "Qotib qolgan lidlarni tekshirish...", "info")
            stagnated = await self.flag_stagnated_leads()
            add_activity("CRM Audit", f"{stagnated} ta qotib qolgan lidlar aniqlandi.", "info")
            
            # 3. Archive Old Leads (>30 days)
            add_activity("CRM Audit", "Eski lidlarni arxivlash...", "info")
            archived = await self.archive_inactive_leads()
            
            # 4. Audit Data (Missing phones, etc.)
            await self.audit_data_integrity()
            
            add_activity("Night Shift Yakunlandi", "Maintenance cycle muvaffaqiyatli yakunlandi. 👸🛡️", "success")
            logger.info("👸 [NIGHT SHIFT] Maintenance cycle completed successfully.")
            return True
        except Exception as e:
            logger.error(f"👸 [NIGHT SHIFT ERROR] Maintenance failed: {e}")
            add_activity("Night Shift Xatolik", str(e), "error")
            return False

    async def deduplicate_contacts(self):
        """Find contacts with shared phones and tag them for merging."""
        logger.info("👸 [NIGHT SHIFT] Scanning for duplicate contacts...")
        # Get all leads (which include contact info)
        leads = await self.amocrm.get_leads_detailed(limit=250)
        
        phone_map = {} # phone -> [contact_ids]
        duplicates_found = 0
        
        for lead in leads:
            phone = self.amocrm.get_lead_phone(lead['id'])
            if phone and phone != "Raqam yo'q":
                clean_phone = "".join(filter(str.isdigit, phone))[-9:]
                if clean_phone not in phone_map:
                    phone_map[clean_phone] = []
                
                # Get the contact ID linked to this lead
                # (Note: AmoCRM leads have contacts in _embedded)
                # But get_lead_phone already did some work. 
                # Let's assume we tag the lead as having a duplicate contact.
                phone_map[clean_phone].append(lead['id'])

        for phone, lead_ids in phone_map.items():
            if len(lead_ids) > 1:
                # Multiple leads/contacts for the same phone
                # Tag all but the first one (or all of them) as POTENTIAL_DUPLICATE
                for l_id in lead_ids:
                    await self.amocrm.add_lead_tag(l_id, "POTENTIAL_DUPLICATE")
                duplicates_found += 1
        
        logger.info(f"👸 [NIGHT SHIFT] Identified {duplicates_found} duplicate groups.")
        return duplicates_found

    async def flag_stagnated_leads(self):
        """Tag leads that haven't moved in 7 days."""
        logger.info("👸 [NIGHT SHIFT] Checking for stagnated leads...")
        leads = await self.amocrm.get_leads_detailed(limit=250)
        now = datetime.now()
        flagged_count = 0
        
        for lead in leads:
            # Skip Won/Lost
            if lead.get('status_id') in [142, 143]: continue
            
            updated_at = datetime.fromtimestamp(lead.get('updated_at', 0))
            if (now - updated_at).days >= 7:
                await self.amocrm.add_lead_tag(lead['id'], "STAGNATED_7_DAYS")
                # Create a task for the responsible user
                resp_id = lead.get('responsible_user_id')
                if resp_id:
                    deadline = int(time.time()) + 3600 * 24 # 24 hours to fix
                    await self.amocrm.create_task(
                        element_id=lead['id'],
                        text="⚠️ Stagnatsiya! Mijoz bilan 7 kundan beri yangilik yo'q. Bog'laning yoki yoping.",
                        complete_till=deadline
                    )
                flagged_count += 1
        
        logger.info(f"👸 [NIGHT SHIFT] Flagged {flagged_count} stagnated leads.")
        return flagged_count

    async def archive_inactive_leads(self):
        """Move 30+ day inactive leads to 'Archive' status."""
        # For now, just tag them as ARCHIVE_CANDIDATE
        leads = await self.amocrm.get_leads_detailed(limit=250)
        now = datetime.now()
        archived_count = 0
        
        for lead in leads:
            if lead.get('status_id') in [142, 143]: continue
            updated_at = datetime.fromtimestamp(lead.get('updated_at', 0))
            if (now - updated_at).days >= 30:
                await self.amocrm.add_lead_tag(lead['id'], "ARCHIVE_CANDIDATE")
                archived_count += 1
        
        logger.info(f"👸 [NIGHT SHIFT] Marked {archived_count} leads for archiving.")
        return archived_count

    async def audit_data_integrity(self):
        """Audit for missing phone numbers and other data."""
        leads = await self.amocrm.get_leads_detailed(limit=250)
        audit_count = 0
        
        for lead in leads:
            phone = self.amocrm.get_lead_phone(lead['id'])
            if not phone or phone == "Raqam yo'q":
                await self.amocrm.add_lead_tag(lead['id'], "MISSING_PHONE")
                audit_count += 1
        
        logger.info(f"👸 [NIGHT SHIFT] Audited {audit_count} leads with missing info.")
        return audit_count
