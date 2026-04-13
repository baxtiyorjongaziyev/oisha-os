import sqlite3
import datetime
import os
import sys
import logging
from telegram.ext import Application
import asyncio
from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add current path to import bot modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from database import Database

from agents.researcher_agent import ResearcherAgent

async def generate_ai_message(user_id: int, prompt: str):
    """AI orqali dinamik va samimiy xabar yaratish."""
    # API keylarni yuklash
    api_keys = {
        "gemini": os.environ.get("GEMINI_API_KEY") or getattr(config, "GEMINI_API_KEY", ""),
        "groq": os.environ.get("GROQ_API_KEY", "")
    }
    
    agent = ResearcherAgent("proactive_bot", config.system_instruction, api_keys)
    # ResearcherAgent ning process_task metodidan foydalanamiz (u fallback ga ega)
    response = await agent.process_task(user_id, prompt)
    return response

async def send_proactive_followups():
    """Bazadagi idle foydalanuvchilarni topadi va AI tomonidan yaratilgan follow-up yuboradi."""
    logger.info("Proactive follow-up job started...")
    
    bot_token = os.environ.get("BOT_TOKEN") or config.BOT_TOKEN
    if not bot_token: return
        
    app = Application.builder().token(bot_token).build()
    db = Database()
    now = datetime.datetime.now()
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, first_name, service_type, last_seen, meeting_time, meeting_status FROM users WHERE is_lead_forwarded != 2")
            rows = cursor.fetchall()
            
            for row in rows:
                user_id, first_name, service_type, last_seen_str, meeting_time, meeting_status = row
                if not last_seen_str: continue

                last_seen = datetime.datetime.fromisoformat(last_seen_str)
                hours_diff = (now - last_seen).total_seconds() / 3600
                
                message = None
                if meeting_status == 'scheduled' and hours_diff > 2:
                    prompt = f"Mijoz {first_name} bilan uchrashuv belgilangan edi. U hozir jim. Unga samimiy, Oisha uslubida eslatma yozing. 'Eslab qoldingizmi' kabi shablonlardan qoching. Insoniy va iliq bo'lsin."
                    message = await generate_ai_message(user_id, prompt)
                    cursor.execute("UPDATE users SET meeting_status = 'completed', last_seen = ? WHERE user_id = ?", (now.isoformat(), user_id))
                    
                elif not meeting_time and 24 <= hours_diff <= 48:
                    prompt = f"Mijoz {first_name} bilan {service_type or 'loyiha'} haqida gaplashgan edik. 1 kundan beri yozmadi. Unga juda samimiy, xuddi Baxtiyorjon akaning yordamchisi kabi, unga qiziqish bildirib xabar yozing. Botligingiz bilinmasin."
                    message = await generate_ai_message(user_id, prompt)
                    cursor.execute("UPDATE users SET last_seen = ? WHERE user_id = ?", (now.isoformat(), user_id))
                    
                if message:
                    try:
                        await app.bot.send_message(chat_id=user_id, text=message)
                        conn.commit()
                        await asyncio.sleep(2)
                    except Exception as e:
                        logger.error(f"[SEND ERROR] {user_id}: {e}")
    except Exception as e:
        logger.error(f"[DB ERROR in Proactive] {e}")

async def send_daily_report():
    """Kunlik muloqotlar tahlilini shakllantirib Owner va Team-ga yuborish."""
    logger.info("Detailed daily report job started...")
    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    owner_id = getattr(config, "OWNER_ID", None)
    group_id = getattr(config, "CRM_GROUP_ID", None)
    
    if not (bot_token and owner_id): 
        logger.warning("[REPORT] Missing token or owner_id")
        return

    app = Application.builder().token(bot_token).build()
    db = Database()
    
    # 1. Statistikani olish
    stats = db.get_daily_report_stats()
    
    # 2. Barcha chatlarni olish (Oxirgi 24 soat)
    chats = db.get_daily_chats_summary()
    
    if not chats:
        logger.info("[REPORT] Oxirgi 24 soatda muloqotlar bo'lmagan.")
        return

    # 3. Chatlarni matn ko'rinishiga keltirish
    full_chats_text = ""
    for uid, data in chats.items():
        full_chats_text += f"\n👤 {data['name']} (@{data['username']}):\n"
        full_chats_text += "\n".join(data['messages'][-10:]) # Oxirgi 10 ta xabar (limit uchun)
        full_chats_text += "\n" + "-"*20

    # 4. OWNER REPORT (Detailed)
    boss_prompt = (
        f"Siz Baxtiyorjon akaning shaxsiy AI PM-i Oishasiz. Bugungi hisobot:\n"
        f"Statistika: Leads: {stats['active_leads']}, Meetings: {stats['meetings']}, Sales: {stats['completed_pays']}.\n\n"
        f"Mana barcha chatlar tafsiloti:\n{full_chats_text}\n\n"
        f"Ushbu ma'lumotlarni tahlil qiling va Baxtiyorjon akaga shaxsan:\n"
        f"1. Har bir mijoz bilan nima gap bo'lganini qisqacha (1 gapda) ayting.\n"
        f"2. Qaysi biri 'sifatli lead' ekanini va qayerda akam aralashishi kerakligini ayting.\n"
        f"3. Umumiy xulosa bering. Oisha uslubida, juda samimiy va professional bo'lsin."
    )
    boss_report = await generate_ai_message(999, boss_prompt)
    
    # 5. TEAM REPORT (Actionable)
    team_prompt = (
        f"Bugungi umumiy muloqotlar tahlili:\n{full_chats_text}\n\n"
        f"Jamoa (Team) uchun faqat foydali va muhim qismlarni ajratib bering:\n"
        f"- Yangi kelgan topshiriqlar.\n"
        f"- Qiziqish bildirgan yangi potensial mijozlar ro'yxati.\n"
        f"- Jamoaga ruhlantiruvchi so'zlar. Oisha uslubida."
    )
    team_report = await generate_ai_message(999, team_prompt)

    # 6. Yuborish
    try:
        # Ownerga yuborish
        await app.bot.send_message(chat_id=owner_id, text=f"💎 <b>DETAILED BOSS REPORT</b> 💎\n\n{boss_report}", parse_mode="HTML")
        
        # Jamoaga (CRM Group) yuborish (agar guruh ID bo'lsa)
        if group_id:
            msg_id = getattr(config, 'CRM_TOPIC_ID', None)
            await app.bot.send_message(chat_id=group_id, text=f"📢 <b>TEAM DAILY BRIEF</b> 📢\n\n{team_report}", parse_mode="HTML", message_thread_id=msg_id)
            
        logger.info("[DAILY REPORT] Owner va Team-ga yuborildi.")
    except Exception as e:
        logger.error(f"[XATO] Daily Report sending: {e}")

async def send_morning_briefing():
    """Ertalabki reja va jamoaga ruhlantiruvchi briefing yuborish."""
    logger.info("Morning briefing job started...")
    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "CRM_GROUP_ID", None)
    if not (bot_token and group_id): return

    app = Application.builder().token(bot_token).build()
    
    prompt = "Bugun dushanba (yoki mos kun). Jamoaga xayrli tong tilang, ularni ruhlantiring va bugun Baxtiyorjon aka bilan ajoyib natijalar kutayotganingizni Oisha uslubida, juda samimiy yozing."
    briefing = await generate_ai_message(999, prompt)
    
    try:
        await app.bot.send_message(chat_id=group_id, text=briefing, parse_mode="HTML")
        logger.info("[MORNING BRIEFING] Yuborildi.")
    except Exception as e:
        logger.error(f"[XATO] Morning briefing: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Proactive AI Worker")
    parser.add_argument("--job", choices=["followup", "report", "briefing"], default="followup", help="Kaysi vazifani bajarish kerak?")
    args = parser.parse_args()
    
    if args.job == "followup":
        asyncio.run(send_proactive_followups())
    elif args.job == "report":
        asyncio.run(send_daily_report())
    elif args.job == "briefing":
        asyncio.run(send_morning_briefing())
