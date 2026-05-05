from telethon import TelegramClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")

if not api_id or not api_hash:
    print("Xatolik: .env faylida API_ID yoki API_HASH topilmadi!")
    exit(1)

session_name = "scraper_session"
client = TelegramClient(session_name, int(api_id), api_hash)


async def main():
    print("Telegramga ulanmoqda...")
    await client.start()

    print("✅ Muvaffaqiyatli ulandi!")

    me = await client.get_me()
    my_id = me.id

    filename = "training_data.txt"
    total_messages = 0
    total_chats = 0

    limit_chats = 1000  # Foydalanuvchi so'rovi bo'yicha

    print("\n� AVTOMATIK YUKLASH BOSHLANDI!")
    print(
        f"Oxirgi {limit_chats} ta chat tekshirilmoqda. Bu biroz vaqt olishi mumkin...\n"
    )

    with open(filename, "w", encoding="utf-8") as f:
        f.write("Mening yozishmalarim tarixi (Auto-Export Telethon 1000).\n\n")

        async for dialog in client.iter_dialogs(limit=limit_chats):
            # Faqat shaxsiy chatlar (guruh va botlar emas)
            if not dialog.is_user:
                continue

            # Botlarni chiqarib tashlash
            if hasattr(dialog.entity, "bot") and dialog.entity.bot:
                continue

            chat_name = dialog.name or "Unknown"
            print(f"📥 O'qilmoqda: {chat_name}...")

            chat_msgs = []
            # Har bir chatdan oxirgi 300 ta xabar
            async for msg in client.iter_messages(dialog.id, limit=300):
                if not msg.text or len(msg.text) < 2:
                    continue
                sender = "ME" if msg.sender_id == my_id else "OTHER"
                chat_msgs.append(f"{sender}: {msg.text}")

            if chat_msgs:
                f.write(f"--- Chat with {chat_name} ---\n")
                for m in reversed(chat_msgs):
                    f.write(m + "\n")
                    total_messages += 1
                f.write("\n\n")
                total_chats += 1

    print(
        f"\n🎉 TAYYOR! Jami {total_chats} ta chatdan {total_messages} ta xabar saqlandi."
    )
    print(f"Fayl: {os.path.abspath(filename)}")
    print(
        "\nEndi bu faylni serverga yuklang (/root/telegram_bot/ papkasiga) va botni restart qiling."
    )


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
