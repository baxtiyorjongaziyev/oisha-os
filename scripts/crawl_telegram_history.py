"""
Oisha-OS: Telegram 3 yillik arxivini avtonom tahlil qilish skripti.

Terminalda bittalab soʻrab oʻtirmaydi — fonda sekin, xavfsiz va tinch
barcha suhbatlarni tahlil qilib, biznes lidlarni ajratadi va hisobot tayyorlaydi.

Ishga tushirish:
    python scripts/crawl_telegram_history.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from telethon import TelegramClient
from telethon.sessions import StringSession

from src.database import Database
from src.services.ai.history_crawler import TelegramHistoryCrawler
from src.services.corporate_sales.repository import CorporateSalesRepository
from src.settings import settings

DEFAULT_API_ID = 2040
DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"


async def main() -> None:
    print("\n" + "=" * 65)
    print("🚀 OISHA-OS | TELEGRAM 3 YILLIK ARXIVINI AVTONOM TAHLIL QILISH")
    print("=" * 65)
    print("⚡ Bittalab tanlash shart emas — tizim fonda barcha suhbatlarni")
    print("   oʻzi kezib chiqadi, oilaviy suhbatlarni chetlab oʻtadi,")
    print("   ovozli xabarlarni STT qiladi va biznes dosyelarni toʻplaydi.\n")

    db = Database()
    repo = CorporateSalesRepository(db)
    await repo.init_tables()

    sellers = await repo.get_all_active_sellers()
    if not sellers:
        print("❌ Birorta ham ulangan sotuvchi yoki shaxsiy hisob topilmadi!")
        print("Avval '.\\connect_sellers.bat' orqali raqamingizni ulang.")
        return

    seller = sellers[0]
    print(f"👤 Hisob: {seller.name} ({seller.phone})")
    print("🔌 Telegramga xavfsiz ulanilmoqda...")

    api_id = settings.API_ID or DEFAULT_API_ID
    api_hash = settings.API_HASH or DEFAULT_API_HASH

    client = TelegramClient(StringSession(seller.session_string), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print("❌ Sessiya eskirgan. Qayta ulaning.")
        await client.disconnect()
        return

    crawler = TelegramHistoryCrawler(repo=repo, rate_limit_seconds=2.0)

    async def on_progress(idx: int, name: str) -> None:
        print(f"[{idx:03d}] 🔍 Tekshirilmoqda: {name} (ovozli xabarlar STT qilinmoqda)...")

    target_leads = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5

    try:
        print(f"⏳ Arxivni avtonom tahlil qilish boshlandi (maqsad: {target_leads} ta eng istiqbolli mijoz)...")
        leads = await crawler.crawl_history(
            client, max_dialogs=300, target_leads=target_leads, progress_callback=on_progress
        )

        print("\n" + "=" * 65)
        print(f"🎉 TAHLIL YAKUNLANDI! Topilgan biznes-lidlar soni: {len(leads)} ta")
        print("=" * 65)

        digest = crawler.generate_digest_markdown(leads)
        out_path = os.path.join("data", "telegram_history_digest.md")
        os.makedirs("data", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(digest)

        print(f"📁 Toʻliq hisobot saqlandi: {out_path}")
        print("🎯 Barcha lidlar bazaga muhrlandi va sotuvga tayyorlandi!\n")

        # Telefondan foydalanayotgan Owner uchun Saqlangan xabarlar (Saved Messages)ga yuborish
        try:
            print("📲 Natijalar Telegram Saqlangan xabarlaringizga (Saved Messages) yuborilmoqda...")
            header = (
                f"🚀 **OISHA-OS | 3 YILLIK ARXIV TAHLILI YAKUNLANDI**\n\n"
                f"📊 Jami topilgan biznes-lidlar: {len(leads)} ta\n"
                f"Quyida eng istiqbolli mijozlar va nusxalab yuborish uchun **tayyor xabarlar** keltirilgan 👇\n\n"
            )
            current_chunk = header
            for idx, lead in enumerate(leads[:10], 1):
                item = (
                    f"**{idx}. {lead.full_name}** ({lead.business_domain})\n"
                    f"💼 Lavozim: {lead.estimated_role} | Toʻlov: {lead.solvency_level}\n"
                    f"🧊 Muz yorar: _{lead.key_icebreaker}_\n\n"
                    f"💬 **Yuborish uchun tayyor xabar (ustiga bosing - nusxalanadi):**\n"
                    f"`{lead.ready_to_send_script}`\n\n"
                    f"────────────────────\n"
                )
                if len(current_chunk) + len(item) > 3800:
                    await client.send_message("me", current_chunk)
                    current_chunk = ""
                current_chunk += item

            if current_chunk.strip():
                await client.send_message("me", current_chunk)
            print("✅ Muvaffaqiyatli! Telefondagi Telegramingizga (Saved Messages) yuborildi.")
        except Exception as exc:
            print(f"⚠️ Telegramga yuborishda xatolik: {exc}")

    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
