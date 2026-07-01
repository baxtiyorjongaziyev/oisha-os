import logging
import os
import time
from datetime import datetime
from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.lead_classifier import LeadClassifier
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
            add_activity(
                "CRM Audit", f"{dupes} ta dublikat aniqlandi va belgilandi.", "success"
            )

            # 2. Flag Stagnated Leads (>7 days)
            add_activity("CRM Audit", "Qotib qolgan lidlarni tekshirish...", "info")
            stagnated = await self.flag_stagnated_leads()
            add_activity(
                "CRM Audit", f"{stagnated} ta qotib qolgan lidlar aniqlandi.", "info"
            )

            # 3. Archive Old Leads (>30 days)
            add_activity("CRM Audit", "Eski lidlarni arxivlash...", "info")
            await self.archive_inactive_leads()

            # 4. Audit Data (Missing phones, etc.)
            await self.audit_data_integrity()

            # 5. AI Lead Classification (audio + notes tahlili)
            add_activity("CRM Audit", "AI klassifikatsiya boshlandi (audio/notes)...", "info")
            classified = await self.classify_leads_ai()
            add_activity(
                "CRM Audit",
                f"AI klassifikatsiya: {classified} ta keraksiz sdelka aniqlandi.",
                "success",
            )

            add_activity(
                "Night Shift Yakunlandi",
                "Maintenance cycle muvaffaqiyatli yakunlandi. 👸🛡️",
                "success",
            )
            logger.info("👸 [NIGHT SHIFT] Maintenance cycle completed successfully.")
            return True
        except Exception as e:
            logger.error(f"👸 [NIGHT SHIFT ERROR] Maintenance failed: {e}")
            add_activity("Night Shift Xatolik", str(e), "error")
            return False

    async def deduplicate_contacts(self):
        """Dublikat kontaktlarni topib, birlashtrish (merge)."""
        logger.info("👸 [NIGHT SHIFT] Scanning and merging duplicate contacts...")
        leads = await self.amocrm.get_leads_detailed(limit=250)

        # phone -> [{lead_id, contact_id, updated_at, price}]
        phone_map = {}
        merged_count = 0

        for lead in leads:
            lead_id = lead["id"]
            # Kontakt ID va telefon olish
            contact_id = self._get_contact_id_from_lead(lead)
            if not contact_id:
                continue

            phone = self.amocrm.get_lead_phone(lead_id)
            if not phone or phone == "Raqam yo'q":
                continue

            clean_phone = "".join(filter(str.isdigit, phone))[-9:]
            if not clean_phone:
                continue

            if clean_phone not in phone_map:
                phone_map[clean_phone] = []

            phone_map[clean_phone].append({
                "lead_id": lead_id,
                "contact_id": contact_id,
                "updated_at": lead.get("updated_at", 0),
                "price": lead.get("price", 0),
                "status_id": lead.get("status_id"),
            })

        for phone, entries in phone_map.items():
            if len(entries) <= 1:
                continue

            # Eng yangi yoki eng qimmat sdelkani asosiy (target) qilib olish
            target = max(entries, key=lambda e: (e["price"], e["updated_at"]))
            sources = [e for e in entries if e["contact_id"] != target["contact_id"]]

            if not sources:
                continue

            # Kontaktlarni birlashtrish
            source_contact_ids = list(set(e["contact_id"] for e in sources))
            success = self.amocrm.merge_contacts(target["contact_id"], source_contact_ids)

            if success:
                merged_count += 1
                # Source leadlarni target kontaktga ko'chirish
                for entry in sources:
                    if entry["lead_id"] != target["lead_id"]:
                        self.amocrm.move_lead_to_contact(entry["lead_id"], target["contact_id"])

                logger.info(
                    f"👸 [MERGE] {phone}: {len(source_contact_ids)} kontakt "
                    f"-> {target['contact_id']} ga birlashtirildi"
                )
            else:
                # Merge API ishlamasa, tag qo'yib qo'yamiz
                for entry in entries:
                    await self.amocrm.add_lead_tag(entry["lead_id"], "POTENTIAL_DUPLICATE")

        logger.info(f"👸 [NIGHT SHIFT] Merged {merged_count} duplicate groups.")
        return merged_count

    def _get_contact_id_from_lead(self, lead: dict) -> int | None:
        """Lead ichidagi birinchi kontakt ID ni olish."""
        contacts = lead.get("_embedded", {}).get("contacts", [])
        if contacts:
            return contacts[0].get("id")
        return None

    async def flag_stagnated_leads(self):
        """Tag leads that haven't moved in 7 days."""
        logger.info("👸 [NIGHT SHIFT] Checking for stagnated leads...")
        leads = await self.amocrm.get_leads_detailed(limit=250)
        now = datetime.now()
        flagged_count = 0

        for lead in leads:
            # Skip Won/Lost
            if lead.get("status_id") in [142, 143]:
                continue

            updated_at = datetime.fromtimestamp(lead.get("updated_at", 0))
            if (now - updated_at).days >= 7:
                await self.amocrm.add_lead_tag(lead["id"], "STAGNATED_7_DAYS")
                # Create a task for the responsible user
                resp_id = lead.get("responsible_user_id")
                if resp_id:
                    deadline = int(time.time()) + 3600 * 24  # 24 hours to fix
                    await self.amocrm.create_task(
                        element_id=lead["id"],
                        text="⚠️ Stagnatsiya! Mijoz bilan 7 kundan beri yangilik yo'q. Bog'laning yoki yoping.",
                        complete_till=deadline,
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
            if lead.get("status_id") in [142, 143]:
                continue
            updated_at = datetime.fromtimestamp(lead.get("updated_at", 0))
            if (now - updated_at).days >= 30:
                await self.amocrm.add_lead_tag(lead["id"], "ARCHIVE_CANDIDATE")
                archived_count += 1

        logger.info(f"👸 [NIGHT SHIFT] Marked {archived_count} leads for archiving.")
        return archived_count

    async def audit_data_integrity(self):
        """Audit for missing phone numbers and other data."""
        leads = await self.amocrm.get_leads_detailed(limit=250)
        audit_count = 0

        for lead in leads:
            phone = self.amocrm.get_lead_phone(lead["id"])
            if not phone or phone == "Raqam yo'q":
                await self.amocrm.add_lead_tag(lead["id"], "MISSING_PHONE")
                audit_count += 1

        logger.info(f"👸 [NIGHT SHIFT] Audited {audit_count} leads with missing info.")
        return audit_count

    async def classify_leads_ai(self) -> int:
        """AI orqali sdelkalarni klassifikatsiya qilish (audio + notes tahlili)."""
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        if not gemini_key:
            logger.warning("[NIGHT SHIFT] GEMINI_API_KEY yo'q, AI klassifikatsiya o'tkazildi.")
            return 0

        try:
            classifier = LeadClassifier(self.amocrm, gemini_key)
            results = await classifier.classify_all_active_leads()
            tagged = await classifier.tag_unnecessary_leads(results)

            summary = classifier.get_summary()
            logger.info(
                f"👸 [NIGHT SHIFT] AI Classification: "
                f"total={summary['total']}, unnecessary={summary['unnecessary_count']}"
            )
            return tagged
        except Exception as e:
            logger.error(f"[NIGHT SHIFT] AI classification error: {e}")
            return 0
