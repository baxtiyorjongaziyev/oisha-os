"""
Korporativ sotuvchilarni Telegram orqali Oisha-OS ga ulash skripti.

Ushbu skript har bir sotuvchining korporativ raqami uchun xavfsiz StringSession
yaratadi va uni Oisha-OS maʼlumotlar bazasiga saqlaydi.

Ishga tushirish:
    python scripts/connect_corporate_seller.py
"""
from __future__ import annotations

import asyncio
import getpass
import os
import sys
from typing import Optional

# Loyiha ildiz yoʻlini qoʻshish
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

from src.database import Database
from src.services.corporate_sales.repository import CorporateSalesRepository
from src.settings import settings


async def get_db_repository() -> CorporateSalesRepository:
    """Maʼlumotlar bazasi omborini tayyorlash."""
    db = Database()
    repo = CorporateSalesRepository(db)
    await repo.init_tables()
    return repo


async def list_connected_sellers(repo: CorporateSalesRepository) -> None:
    """Uzlangan barcha faol sotuvchilarni chiqarish."""
    sellers = await repo.get_all_active_sellers()
    print("\n" + "=" * 50)
    print("📋 HOZIRDA ULANgan KORPORATIV SOTUVCHILAR:")
    print("=" * 50)
    if not sellers:
        print("  (Hozircha birorta ham korporativ sotuvchi ulanmagan)")
    else:
        for s in sellers:
            print(f"  • ID: {s.seller_id} | Ism: {s.name} | Tel: {s.phone}")
    print("=" * 50 + "\n")


async def authenticate_telegram_session(
    phone: str,
    api_id: int,
    api_hash: str,
) -> Optional[str]:
    """Telethon orqali avtorizatsiyadan oʻtib, StringSession olish."""
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print(f"\n📲 {phone} raqamiga Telegram orqali kod yuborilmoqda...")
        try:
            await client.send_code_request(phone)
        except Exception as exc:
            print(f"❌ Kod yuborishda xatolik: {exc}")
            await client.disconnect()
            return None

        code = input("🔑 Telegramga kelgan 5 xonali kodni kiriting: ").strip()
        try:
            await client.sign_in(phone=phone, code=code)
        except SessionPasswordNeededError:
            pwd = getpass.getpass("🔒 2FA parolini kiriting (ikki bosqichli himoya): ")
            await client.sign_in(password=pwd)
        except Exception as exc:
            print(f"❌ Kod bilan kirishda xatolik: {exc}")
            await client.disconnect()
            return None

    me = await client.get_me()
    session_str = client.session.save()
    first_name = getattr(me, "first_name", "") or ""
    username = getattr(me, "username", "") or "yoʻq"
    print(f"✅ Telegram hisobi tasdiqlandi: {first_name} (@{username})")

    await client.disconnect()
    return session_str


async def test_seller_session(session_string: str, api_id: int, api_hash: str) -> bool:
    """Saqlangan sessiyaning yaroqliligini tekshirish."""
    try:
        client = TelegramClient(StringSession(session_string), api_id, api_hash)
        await client.connect()
        is_auth = await client.is_user_authorized()
        await client.disconnect()
        return is_auth
    except Exception as exc:
        print(f"❌ Sessiyani tekshirishda xatolik: {exc}")
        return False


async def register_new_seller_interactive(
    repo: CorporateSalesRepository,
    api_id: int,
    api_hash: str,
) -> None:
    """Interaktiv rejimda yangi sotuvchini ulash."""
    print("\n➕ YANGI KORPORATIV SOTUVCHINI ULASH")
    print("-" * 40)

    name = input("👤 Sotuvchining ismi (masalan, Sardor): ").strip()
    if not name:
        print("❌ Ism kiritilmadi, bekor qilindi.")
        return

    phone = input("📞 Korporativ telefon raqami (masalan, +998901234567): ").strip()
    if not phone.startswith("+"):
        print("❌ Raqam xalqaro formatda (+) bilan boshlanishi kerak.")
        return

    # Avval bazada bor-yoʻqligini tekshirish
    existing = await repo.get_seller_by_phone(phone)
    if existing:
        ans = input(
            f"⚠️ Ushbu raqam ({existing.name}) allaqachon mavjud. Qayta ulaymizmi? (h/y): "
        ).strip().lower()
        if ans not in ("h", "ha", "y", "yes"):
            print("Bekor qilindi.")
            return

    # Telegram orqali sessiya olish
    session_str = await authenticate_telegram_session(phone, api_id, api_hash)
    if not session_str:
        print("❌ Sessiya yaratilmadi.")
        return

    # Bazaga yozish
    seller = await repo.upsert_seller(
        name=name,
        phone=phone,
        session_string=session_str,
    )
    if seller:
        print(f"\n🎉 MUVAFFAQIYAT! {seller.name} ({seller.phone}) Oisha-OS ga ulandi.")
        print(f"📌 Baza ID: {seller.seller_id}")
    else:
        print("❌ Bazaga saqlashda xatolik yuz berdi.")


async def main() -> None:
    """Asosiy skript nuqtasi."""
    print("\n" + "=" * 55)
    print("🚀 OISHA-OS | KORPORATIV SOTUVCHILARNI ULASH DASTURI")
    print("=" * 55)

    api_id = settings.API_ID
    api_hash = settings.API_HASH

    if not api_id or not api_hash:
        print("\n⚠️ settings.py yoki .env da API_ID / API_HASH topilmadi.")
        print("Telegram MTProto API kalitlarini kiriting (https://my.telegram.org):")
        raw_id = input("🔑 API_ID (raqam): ").strip()
        raw_hash = input("🔑 API_HASH: ").strip()
        if raw_id.isdigit() and raw_hash:
            api_id = int(raw_id)
            api_hash = raw_hash
        else:
            print("❌ Notoʻgʻri API_ID yoki API_HASH kiritildi. Dastur toʻxtatildi.")
            return

    repo = await get_db_repository()
    await list_connected_sellers(repo)

    while True:
        print("\nAMALLAR:")
        print("  1. Yangi sotuvchini ulash")
        print("  2. Mavjud sotuvchilar roʻyxatini koʻrish")
        print("  3. Sotuvchini oʻchirish (nofaol qilish)")
        print("  4. Chiqish")

        choice = input("\nTanlang (1-4): ").strip()

        if choice == "1":
            await register_new_seller_interactive(repo, api_id, api_hash)
        elif choice == "2":
            await list_connected_sellers(repo)
        elif choice == "3":
            seller_id_raw = input("Nofaol qilinadigan Sotuvchi ID sini kiriting: ").strip()
            if seller_id_raw.isdigit():
                ok = await repo.deactivate_seller(int(seller_id_raw))
                if ok:
                    print(f"✅ Sotuvchi #{seller_id_raw} muvaffaqiyatli nofaol qilindi.")
                else:
                    print("❌ Oʻchirishda xatolik.")
            else:
                print("❌ Notoʻgʻri ID.")
        elif choice == "4":
            print("\nXayr!")
            break
        else:
            print("❌ Notoʻgʻri tanlov.")


if __name__ == "__main__":
    asyncio.run(main())
