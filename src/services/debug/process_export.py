import json
import os

# Konfiguratsiya
INPUT_FILE = "result.json"
OUTPUT_FILE = "training_data.txt"
MY_NAME = "Baxtiyor" # O'zingizning Telegram ismingiz (JSON dagi "from" maydoni bilan bir xil bo'lishi kerak)

def process_chat_export():
    if not os.path.exists(INPUT_FILE):
        print(f"Xatolik: {INPUT_FILE} topilmadi! Faylni shu papkaga tashlang.")
        return

    print("Fayl o'qilmoqda... (Katta fayl bo'lsa biroz vaqt oladi)")
    
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    chats = data.get("chats", {}).get("list", [])
    total_messages = 0
    exported_messages = 0

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write("Bu fayl mening yozishmalarim tarixi. Men shu uslubda gapirishim kerak.\n\n")

        for chat in chats:
            chat_name = chat.get("name", "Unknown")
            messages = chat.get("messages", [])
            
            # Faqat shaxsiy chatlar (type: "personal_chat")
            if chat.get("type") != "personal_chat":
                continue

            chat_history = []
            
            for msg in messages:
                if msg.get("type") != "message":
                    continue
                
                text = msg.get("text")
                sender = msg.get("from")

                # Matnli xabarlar (list bo'lsa birlashtiramiz)
                if isinstance(text, list):
                    text_content = ""
                    for part in text:
                        if isinstance(part, str):
                            text_content += part
                        elif isinstance(part, dict):
                            text_content += part.get("text", "")
                    text = text_content
                
                if not text or text == "":
                    continue

                # Qisqa javoblarni chiqarib tashlash (ixtiyoriy)
                # if len(text) < 2: continue

                label = "ME" if sender == MY_NAME else "OTHER"
                chat_history.append(f"{label}: {text}")
                total_messages += 1

            # Agar chatda xabar bo'lsa, yozamiz
            if chat_history:
                out.write(f"--- Chat with {chat_name} ---\n")
                out.write("\n".join(chat_history))
                out.write("\n\n")
                exported_messages += len(chat_history)

    print(f"Tayyor! {total_messages} ta xabardan {exported_messages} tasi saqlandi.")
    print(f"Natija: {OUTPUT_FILE}")

if __name__ == "__main__":
    owner = input(f"Sizning Telegram ismingiz (Default: {MY_NAME}): ")
    if owner:
        MY_NAME = owner
    process_chat_export()
