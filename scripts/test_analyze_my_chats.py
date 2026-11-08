"""
Oisha-OS: Oʻz Telegram suhbatlarini Jon Branding Sales Playbook boʻyicha tahlil qilish testi.

Ushbu skript foydalanuvchining (Owner / Menejer) oxirgi Telegram suhbatlarini oʻqib,
Gemini 1.5 AI orqali tahlil qiladi va amoCRM izohini tayyorlaydi.

Ishga tushirish:
    python scripts/test_analyze_my_chats.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, List, Optional

# Loyiha ildiz yoʻli
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from telethon.sessions import StringSession

from src.database import Database
from src.services.ai.quality_analyzer import QualityAnalyzer
from src.services.corporate_sales.reporter import CorporateSalesReporter
from src.services.corporate_sales.repository import CorporateSalesRepository
from src.settings import settings


DEFAULT_API_ID = 2040
DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"


async def get_sellers(repo: CorporateSalesRepository):
    """Faol sotuvchilar roʻyxatini olish."""
    return await repo.get_all_active_sellers()


async def choose_seller(sellers: List[Any]) -> Optional[Any]:
    """Tahlil qilinadigan sotuvchi yoki shaxsiy hisobni tanlash."""
    if not sellers:
        print("\n❌ Birorta ham ulangan hisob topilmadi!")
        print("Iltimos, avval quyidagi buyruq orqali oʻz raqamingizni ulang:")
        print("    .\\connect_sellers.bat\n")
        return None

    if len(sellers) == 1:
        return sellers[0]

    print("\nQaysi hisob suhbatlarini tahlil qilmoqchisiz?")
    for idx, s in enumerate(sellers, 1):
        print(f"  {idx}. {s.name} ({s.phone})")

    choice = input(f"\nTanlang (1-{len(sellers)}): ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(sellers):
            return sellers[idx]
    except ValueError:
        pass
    return sellers[0]


async def fetch_recent_dialogs(client: TelegramClient, limit: int = 10) -> List[Any]:
    """Oxirgi shaxsiy dialoglarni yuklab olish."""
    dialogs = []
    async for dialog in client.iter_dialogs(limit=limit * 2):
        if dialog.is_user and not getattr(dialog.entity, "bot", False):
            dialogs.append(dialog)
            if len(dialogs) >= limit:
                break
    return dialogs


def format_dialog_title(dialog: Any) -> str:
    """Dialog sarlavhasini chiroyli formatlash."""
    entity = dialog.entity
    first_name = getattr(entity, "first_name", "") or ""
    last_name = getattr(entity, "last_name", "") or ""
    name = f"{first_name} {last_name}".strip() or "Nomaʼlum mijoz"
    phone = getattr(entity, "phone", "")
    phone_str = f" (+{phone})" if phone else ""
    last_msg = (dialog.message.message or "").replace("\n", " ")[:40]
    return f"{name}{phone_str} — \"{last_msg}...\""


async def fetch_dialog_history(client: TelegramClient, peer: Any, limit: int = 20) -> str:
    """Mijoz bilan oxirgi xabarlar tarixini matnga aylantirish."""
    messages = []
    async for msg in client.iter_messages(peer, limit=limit):
        if not msg.message and not msg.voice:
            continue
        text = msg.message or "[Ovozli xabar]"
        sender = "Menejer" if msg.out else "Mijoz"
        messages.append(f"{sender}: {text}")

    messages.reverse()
    return "\n".join(messages)


def print_analysis_results(analysis: Any) -> None:
    """Tahlil natijalarini ekranga chiroyli chiqarish."""
    print("\n" + "=" * 60)
    print("📊 JON BRANDING SALES PLAYBOOK | AI TAHLIL NATIJASI")
    print("=" * 60)
    print(f"🎯 Umumiy ball:       {analysis.total_score} / 100")
    print(f"🏆 Toifa:             {analysis.category}")
    print(f"📈 Natija:            {analysis.deal_outcome}")
    print(f"🗣 Mijoz ulushi:      {analysis.client_talk_ratio}%")
    print(f"🧑‍💼 Menejer ulushi:   {analysis.agent_talk_ratio}%")
    print("-" * 60)

    print("\n📋 METRIKALAR BOʻYICHA BAHOLASH:")
    for metric_name, score in analysis.metric_scores.items():
        print(f"  • {metric_name:25}: {score:3.0f} ball")

    if analysis.deal_reasons:
        print("\n🔍 XULOSA VA SABABLAR:")
        for r in analysis.deal_reasons:
            print(f"  • {r}")

    if analysis.improvement_points:
        print("\n💡 ROP TAVSIYALARI VA KEYINGI QADAM:")
        for p in analysis.improvement_points:
            print(f"  💡 {p}")

    print("=" * 60 + "\n")


async def main() -> None:
    """Asosiy ijrochi funksiya."""
    print("\n" + "=" * 60)
    print("🚀 OISHA-OS | TELEGRAM SUHBATLARINI JONLI AI AUDIT QILISH")
    print("=" * 60)

    db = Database()
    repo = CorporateSalesRepository(db)
    await repo.init_tables()

    sellers = await get_sellers(repo)
    seller = await choose_seller(sellers)
    if not seller:
        return

    api_id = settings.API_ID or DEFAULT_API_ID
    api_hash = settings.API_HASH or DEFAULT_API_HASH

    print(f"\n🔌 {seller.name} hisobiga ulanilmoqda...")
    client = TelegramClient(StringSession(seller.session_string), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print("❌ Sessiya eskirgan yoki ruxsat berilmagan. Qayta ulaning.")
        await client.disconnect()
        return

    try:
        print("📥 Oxirgi mijozlar roʻyxati yuklanmoqda...")
        dialogs = await fetch_recent_dialogs(client, limit=8)
        if not dialogs:
            print("❌ Birorta ham shaxsiy dialog topilmadi.")
            return

        print("\nOxirgi suhbatlar:")
        for idx, d in enumerate(dialogs, 1):
            print(f"  {idx}. {format_dialog_title(d)}")

        choice = input(f"\nQaysi mijoz bilan suhbatni tahlil qilamiz? (1-{len(dialogs)}): ").strip()
        try:
            sel_idx = int(choice) - 1
            if not (0 <= sel_idx < len(dialogs)):
                sel_idx = 0
        except ValueError:
            sel_idx = 0

        target_dialog = dialogs[sel_idx]
        peer_name = getattr(target_dialog.entity, "first_name", "Mijoz")
        phone = getattr(target_dialog.entity, "phone", "")
        print(f"\n⏳ \"{peer_name}\" bilan oxirgi 20 ta xabar oʻqilmoqda...")

        history_text = await fetch_dialog_history(client, target_dialog.entity, limit=20)
        if not history_text.strip():
            print("❌ Suhbatda tahlil qilish uchun xabarlar yetarli emas.")
            return

        print("🤖 Gemini 1.5 suhbatni Jon Branding Playbook boʻyicha tahlil qilmoqda...")
        analyzer = QualityAnalyzer()
        analysis = await analyzer.analyze_conversation_ai(
            conversation_text=history_text,
            conversation_id=f"test_{target_dialog.id}",
            manager_name=seller.name,
        )

        print_analysis_results(analysis)

        # AmoCRM sinxronizatsiyasi taklifi
        reporter = CorporateSalesReporter()
        note_text = reporter.format_amocrm_note(analysis)
        print("📝 amoCRMʼGA TUSHADIGAN IZOH MATNI:")
        print("-" * 40)
        print(note_text)
        print("-" * 40)

        if phone:
            ans = input("\nUshbu tahlilni amoCRMʼdagi mijoz kartochkasiga yozamizmi? (h/y): ").strip().lower()
            if ans in ("h", "ha", "y", "yes"):
                print("⏳ amoCRM ga sinxronlanmoqda...")
                synced = await reporter._sync_note_to_amocrm(
                    f"+{phone}" if not phone.startswith("+") else phone,
                    note_text,
                )
                if synced:
                    print("✅ Muvaffaqiyatli! amoCRM kartochkasiga izoh qoʻshildi.")
                else:
                    print("⚠️ amoCRMʼda bu raqamli faol bitim topilmadi yoki xatolik yuz berdi.")

    finally:
        await client.disconnect()
        print("\nUlanish yopildi. Sinov yakunlandi.")


if __name__ == "__main__":
    asyncio.run(main())
