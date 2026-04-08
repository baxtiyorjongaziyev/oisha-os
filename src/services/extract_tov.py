import asyncio
import logging
import json
import os
import random
from telethon import TelegramClient, functions, types
from datetime import datetime, timezone

from config import API_ID, API_HASH
from settings import settings
import google.generativeai as genai

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SESSION_NAME = "userbot_session"

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY.get_secret_value())
model = genai.GenerativeModel('gemini-2.0-flash')

# Business Folders/Folders to Study Tone of Voice
TARGET_FOLDERS = [
    "Aktiv loyiha",
    "Lead",
    "Closed Costu", 
    "KP Yuborildi",
    "To'lov kutil",
    "Faol mijoz"
]

async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    
    logger.info("Biznes papkalarni qidirish va Tone of Voice tahlilini boshlash... 📈")
    
    # 1. Get Dialog Filters (Folders)
    try:
        dialog_filters = await client(functions.messages.GetDialogFiltersRequest())
        target_peers = set()
        
        found_folders = []
        for f in dialog_filters.filters:
            if isinstance(f, types.DialogFilter):
                # Search for target folder names (partial match allowed)
                # Since title can be TextWithEntities, use .text or str()
                title_text = f.title.text if hasattr(f.title, 'text') else str(f.title)
                is_target = any(target.lower() in title_text.lower() for target in TARGET_FOLDERS)
                if is_target:
                    found_folders.append(title_text)
                    # Add all peer accounts from this folder
                    all_peers = (f.include_peers or []) + (f.pinned_peers or [])
                    for peer in all_peers:
                        # Extract the peer ID or other identifier
                        if hasattr(peer, 'user_id'):
                            target_peers.add(peer.user_id)
                        elif hasattr(peer, 'chat_id'):
                            target_peers.add(peer.chat_id)
                        elif hasattr(peer, 'channel_id'):
                            target_peers.add(peer.channel_id)
        
        if not found_folders:
            logger.error(f"Belgilangan papkalar topilmadi. Mavjud papkalar: {[f.title for f in dialog_filters if hasattr(f, 'title')]}")
            return
            
        logger.info(f"Target papkalar topildi: {found_folders}")
        logger.info(f"Jami {len(target_peers)} ta chat tahlilga olinadi.")
        
    except Exception as e:
        logger.error(f"Papkalar ro'yxatini olishda xato: {e}")
        return

    # 2. Xabarlarni yig'amiz
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    all_my_messages = []
    total_messages_scanned = 0

    # Iterating through all target peers
    for peer_id in target_peers:
        try:
            # We try to get dialog or entity directly
            entity = await client.get_entity(peer_id)
            entity_name = getattr(entity, 'first_name', '') or getattr(entity, 'title', '') or str(peer_id)
            
            logger.info(f"O'qiyapman: {entity_name}...")
            
            # Fetch last 500 messages from "me"
            async for msg in client.iter_messages(entity, from_user='me', offset_date=datetime.now(), limit=500):
                if not msg.text:
                    continue
                if msg.date < start_date:
                    break
                
                text = msg.text.strip()
                if len(text) > 2:
                    all_my_messages.append(text)
                    total_messages_scanned += 1
                
                # Banning prevention & context window management
                if total_messages_scanned >= 5000:
                    break
                    
            if total_messages_scanned >= 5000:
                break
                
        except Exception as e:
            logger.debug(f"Peer {peer_id} tahlilida xato: {e}")
            continue

    logger.info(f"Jami yig'ilgan biznes xabarlar: {len(all_my_messages)} ta.")
    
    if len(all_my_messages) < 30:
        logger.error("Vakillik tahlil qilish uchun xabarlar juda kam!")
        return

    # 3. Yig'ilgan xabarlarni bitta yirik matnga aylantirish
    # We sample if too large, but 5000 typical messages fit into Gemini Flash
    big_text = "\n---\n".join(all_my_messages)
    if len(big_text) > 150000:
        big_text = big_text[:150000]

    # 4. Prompt Engineering for Business ToV
    prompt = f"""
    Siz dunyodagi eng tajribali Tilshunos va Brending Analistisiz.
    Vazifangiz: Mijozimizning Telegramdagi biznes suhbatlari (Aktiv loyiha, Lead va boshqa papkalar) asosida uning professional "Tone of Voice" (ToV) ohangini aniqlash.
    Ushbu ma'lumotlar mijozning faqat o'zi yuborgan haqiqiy xabarlaridir.
    
    Tahlil qilinishi kerak bo'lgan mezonlar:
    1. Ohang: Qanchalik professional yoki erkin? (Masalan: rasmiy ish munosabati yoki ishonchli hamkorlik uslulidami?)
    2. Maxsus so'zlar: Qanday biznes atamalari, slenglar yoki o'zi uchun xos iboralarni ko'p ishlatadi?
    3. Yozuv uslubi: Lotinchami yoki kirillchami? "manga", "man", "bo'ldi" kabi o'zbekona xususiyatlar saqlanadimi?
    4. Struktur: Xabarlar qisqa (masalan "ok", "tushundim") yoki tushuntirishlar bilan uzoqmi?
    5. Emojilar va tinish belgilari: Biznes kontekstida qanchalik foydalanadi?
    
    XULOSA FORMATI:
    Sizdan faqat bitta SYSTEM PROMPT (Qoidalar ro'yxati) ko'rinishida javob kutyapman. 
    Bu matn boshqa bir AI agentiga beriladi va u XUDDI SHU INSONDEK biznes muloqot qilishi kerak.
    
    Promptingiz shunday boshlansin:
    [BUSINESS PERSONA RULES BEGIN]
    ...
    [BUSINESS PERSONA RULES END]
    
    Mana uning haqiqiy biznes xabarlari bazasi:
    {big_text}
    """

    logger.info("AI tahlili boshlandi (Gemini 2.0 Flash)... 👸")
    
    try:
        response = model.generate_content(prompt)
        ai_analysis = response.text.strip()
        
        save_path = "business_tov_persona.md"
        with open(save_path, "w", encoding='utf-8') as f:
            f.write(ai_analysis)
            
        logger.info(f"Ajoyib! Biznes tahlil yakunlandi va '{save_path}' fayliga saqlandi!")
    except Exception as e:
        logger.error(f"AI Analizida muammo: {e}")

if __name__ == "__main__":
    asyncio.run(main())
