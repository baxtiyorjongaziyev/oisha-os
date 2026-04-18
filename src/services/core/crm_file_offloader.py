import asyncio
import logging
import os
import tempfile
from typing import Optional, List, Dict, Any
from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.gdrive import GoogleDriveSync
from src.settings import settings

logger = logging.getLogger(__name__)

class CRMFileOffloader:
    """
    Service to offload files from AmoCRM to Google Drive to save disk space.
    """
    def __init__(self, amocrm: AmoCRMSync, gdrive: GoogleDriveSync):
        self.amo = amocrm
        self.gdrive = gdrive
        self.folder_id = settings.GDRIVE_OFFLOAD_FOLDER_ID

    async def _ensure_folder(self) -> str:
        """Google Drive-da offload papkasi borligini tekshiradi yoki yaratadi."""
        if self.folder_id:
            return self.folder_id

        logger.info("[OFFLOADER] GDRIVE_OFFLOAD_FOLDER_ID topilmadi. Yangi yaratilmoqda...")
        folder_id = self.gdrive.create_folder("Oisha_AmoCRM_Offload")
        if folder_id:
            logger.info(f"[OFFLOADER] Yangi papka yaratildi: {folder_id}")
            self.folder_id = folder_id
            # Kelajakda sozlamalarda qolishi uchun .env yangilanishi tavsiya etiladi (manual)
            return folder_id
        return ""

    async def run(self, dry_run: bool = True, lead_ids: Optional[List[int]] = None):
        """
        Offloading jarayonini ishga tushirish.
        :param dry_run: Haqiqiy o'chirishni amalga oshirmaslik.
        :param lead_ids: Faqat ma'lum lidlar ustida ishlash.
        """
        logger.info(f"🚀 CRM File Offloader boshlandi (Dry Run: {dry_run})")
        
        folder_id = await self._ensure_folder()
        if not folder_id and not dry_run:
            logger.error("❌ Google Drive papkasini aniqlab bo'lmadi. To'xtatildi.")
            return

        # 1. Bitimlarni olish
        if lead_ids:
            leads = []
            for l_id in lead_ids:
                l_data = await self.amo.get_lead(l_id)
                if l_data: leads.append(l_data)
        else:
            leads = await self.amo.get_leads()
        
        logger.info(f"🔍 {len(leads)} ta bitim tahlil qilinmoqda...")

        stats = {"found": 0, "offloaded": 0, "errors": 0}

        for lead in leads:
            lead_id = lead["id"]
            notes = await self.amo.get_lead_notes(lead_id)
            
            for note in notes:
                # AmoCRM-da fayllar 'file' note_type bilan keladi
                if note.get("note_type") == "file":
                    params = note.get("params", {})
                    file_name = params.get("file_name", f"file_{note['id']}")
                    file_uuid = params.get("file_uuid")
                    
                    if not file_uuid: continue

                    stats["found"] += 1
                    logger.info(f"📂 Lead {lead_id}: Fayl aniqlandi - {file_name}")
                    
                    if dry_run:
                        logger.info(f"   [DRY RUN] {file_name} ko'chirilishi mumkin.")
                        stats["offloaded"] += 1
                        continue

                    # 2. Faylni AmoCRM dan yuklab olish
                    try:
                        file_content = self.amo.download_file(file_uuid)
                        if not file_content:
                            logger.error(f"   ❌ Faylni yuklab bo'lmadi: {file_name}")
                            stats["errors"] += 1
                            continue
                        
                        # 3. Vaqtinchalik fayl yaratish va Drive-ga yuklash
                        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
                            tmp.write(file_content)
                            tmp_path = tmp.name
                        
                        try:
                            # Drive-da bitim uchun sub-folder (ixtiyoriy, tartib uchun)
                            # lead_folder = self.gdrive.create_folder(f"Lead_{lead_id}", parent_id=folder_id)
                            # target_folder = lead_folder or folder_id
                            
                            drive_link = self.gdrive.upload_file(tmp_path, folder_id=folder_id)
                            
                            if drive_link:
                                # 4. CRM-da yangi note qoldirish
                                note_text = f"📎 Fayl Google Drive-ga ko'chirildi (Storage Optimization):\n🔗 {drive_link}"
                                self.amo.add_lead_note(lead_id, note_text)
                                
                                # 5. Original faylni o'chirish
                                success = await self.amo.delete_note("leads", lead_id, note["id"])
                                if success:
                                    logger.info(f"   ✅ {file_name} muvaffaqiyatli ko'chirildi va CRM-dan o'chirildi.")
                                    stats["offloaded"] += 1
                                else:
                                    logger.warning(f"   ⚠️ {file_name} ko'chirildi, lekin originalni o'chirib bo'lmadi.")
                            else:
                                logger.error(f"   ❌ Drive-ga yuklashda xato: {file_name}")
                                stats["errors"] += 1
                        finally:
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)
                                
                    except Exception as e:
                        logger.error(f"   ❌ Lead {lead_id} faylini qayta ishlashda xato: {e}")
                        stats["errors"] += 1

        logger.info(f"🏁 Yakunlandi. Topildi: {stats['found']}, Ko'chirildi: {stats['offloaded']}, Xatolar: {stats['errors']}")
        return stats

async def main():
    # Faqat test uchun
    from src.services.core.gdrive import GoogleDriveSync
    amo = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.AMOCRM_REDIRECT_URL
    )
    gdrive = GoogleDriveSync(settings.GSHEET_CREDS_FILE)
    offloader = CRMFileOffloader(amo, gdrive)
    await offloader.run(dry_run=True)

if __name__ == "__main__":
    asyncio.run(main())
