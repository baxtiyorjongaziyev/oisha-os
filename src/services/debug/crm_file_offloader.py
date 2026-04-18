import asyncio
import logging
import os
import requests
from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.gdrive import GoogleDriveSync
from src.settings import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CRMFileOffloader:
    def __init__(self, amocrm: AmoCRMSync, gdrive: GoogleDriveSync):
        self.amo = amocrm
        self.gdrive = gdrive
        self.temp_dir = "tmp/crm_files"
        os.makedirs(self.temp_dir, exist_ok=True)

    async def run(self, dry_run=True):
        logger.info(f"🚀 CRM File Offloader boshlandi (Dry Run: {dry_run})")
        
        # 1. Barcha aktiv bitimlarni olish (limit: 50)
        leads = await self.amo.get_leads()
        logger.info(f"🔍 {len(leads)} ta bitim tekshirilmoqda...")

        total_offloaded = 0
        total_size = 0

        for lead in leads:
            lead_id = lead["id"]
            notes = await self.amo.get_lead_notes(lead_id)
            
            for note in notes:
                # AmoCRM-da fayllar 'file' note_type bilan keladi
                if note.get("note_type") == "file":
                    params = note.get("params", {})
                    # file_uuid, file_name, file_size kabi ma'lumotlar bo'lishi kerak
                    file_name = params.get("file_name", "unnamed_file")
                    file_uuid = params.get("file_uuid")
                    
                    if not file_uuid: continue

                    logger.info(f"📂 Lead {lead_id}: Fayl topildi - {file_name}")
                    
                    if dry_run:
                        total_offloaded += 1
                        continue

                    # 2. Faylni yuklab olish
                    # Eslatma: AmoCRM fayllarni yuklab olish uchun alohida endpoint yoki vaqtinchalik URL talab qilishi mumkin.
                    # Ko'pincha bu api/v4/files orqali bo'ladi.
                    # Hozircha taxminiy endpoint:
                    download_url = f"{self.amo.base_url}/api/v4/files/{file_uuid}/download"
                    # Bu qism AmoCRM API versiyasiga qarab o'zgarishi mumkin.
                    
                    local_path = os.path.join(self.temp_dir, file_name)
                    resp = requests.get(download_url, headers=self.amo._get_headers())
                    
                    if resp.status_code == 200:
                        with open(local_path, "wb") as f:
                            f.write(resp.content)
                        
                        # 3. Google Drive-ga yuklash
                        drive_link = self.gdrive.upload_file(local_path)
                        
                        if drive_link:
                            # 4. AmoCRM-da yangi note qoldirish
                            self.amo.add_lead_note(lead_id, f"📎 Fayl Google Drive-ga ko'chirildi: {drive_link}")
                            
                            # 5. Orginal note-ni o'chirish (Space bo'shatish uchun)
                            success = await self.amo.delete_note("leads", lead_id, note["id"])
                            if success:
                                logger.info(f"✅ Lead {lead_id}: {file_name} ko'chirildi va o'chirildi.")
                                total_offloaded += 1
                        
                        # Tozalash
                        if os.path.exists(local_path):
                            os.remove(local_path)
                    else:
                        logger.error(f"❌ Faylni yuklab bo'lmadi ({file_uuid}): {resp.status_code}")

        logger.info(f"🏁 Yakunlandi. Jami ko'chirilgan fayllar: {total_offloaded}")

async def main():
    amo = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.AMOCRM_REDIRECT_URL
    )
    
    # Google Drive service
    gdrive = GoogleDriveSync(settings.GSHEET_CREDS_FILE)
    
    offloader = CRMFileOffloader(amo, gdrive)
    await offloader.run(dry_run=True) # Initially dry run

if __name__ == "__main__":
    asyncio.run(main())
