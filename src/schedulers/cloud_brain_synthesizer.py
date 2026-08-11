"""Scheduler for AI Promises Tracker (24/7 Cloud Brain Synthesizer)."""
import asyncio
import logging
from src.database import get_db
from src.settings import settings
import google.generativeai as genai

logger = logging.getLogger(__name__)

PROMPT = """
You are the AI "Second Brain" Synthesizer for Oisha-OS.
Analyze the following recent tasks, activities, and communication logs.
Your goal is to extract valuable insights across 5 key dimensions of a Second Brain.

Format your output EXACTLY as a markdown list with these 5 sections:

### 1. 🔄 Context Switching (Key Decisions & Next Actions)
- Extract the absolute next action for active projects so the user can jump right back in without thinking.

### 2. 💡 Content Machine (Ideas & Quotes)
- Extract any interesting thoughts, quotes, or marketing/content ideas mentioned.

### 3. 📜 SOPs & Agent Rules
- Extract any implicit rules, instructions, or workflows that the user mentioned. These will become permanent SOPs.

### 4. 🤝 Personal CRM (Promises Tracker)
- Extract any "Dropped Balls", unfulfilled promises, or pending agreements with specific people.

### 5. 🧩 Pattern Recognition (Connections)
- Find any non-obvious connections between different tasks or problems. How does A relate to B?

If a section has no relevant data, write: "Ma'lumot yo'q."

Data:
{data}
"""

async def _fetch_recent_data():
    try:
        db = get_db()
        conn = await db.get_connection()
        # Fetch recent pending tasks from DB
        cursor = await conn.execute(
            "SELECT title, description FROM tasks WHERE status='Pending' ORDER BY created_at DESC LIMIT 20"
        )
        rows = await cursor.fetchall()
        
        data = "\n".join([f"Task: {r[0]} - {r[1]}" for r in rows])
        return data if data else "No recent data found."
    except Exception as e:
        logger.error(f"[BRAIN_SYNTH] Error fetching data: {e}")
        return ""

async def _generate_insights(data: str) -> str:
    if not data or data == "No recent data found.":
        return "Bugun uchun qolib ketgan va'dalar yo'q."

    gemini_key = settings.GEMINI_API_KEY.get_secret_value() if settings.GEMINI_API_KEY else None
    if not gemini_key:
        return "Gemini API kaliti topilmadi."

    try:
        # Avoid blocking the event loop
        def sync_call():
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(PROMPT.format(data=data))
            return response.text

        result = await asyncio.to_thread(sync_call)
        return result
    except Exception as e:
        logger.error(f"[BRAIN_SYNTH] Gemini API error: {e}")
        return f"Analizda xatolik yuz berdi: {e}"

async def run_brain_synthesizer_cycle(bot_client, target_chat_id: int):
    """Fetches data, runs analysis, and sends digest to Telegram."""
    logger.info("[BRAIN_SYNTH] Starting synthesis cycle...")
    data = await _fetch_recent_data()
    insights = await _generate_insights(data)
    
    if "Ma'lumot yo'q" in insights and insights.count("Ma'lumot yo'q") >= 4:
        logger.info("[BRAIN_SYNTH] No significant new insights found across pillars.")
        return

    message = f"🧠 <b>Second Brain Evolution Digest</b>\n\n{insights}"
    
    try:
        if hasattr(bot_client, "send_message"):
            await bot_client.send_message(
                target_chat_id,
                message,
                parse_mode="HTML"
            )
            logger.info("[BRAIN_SYNTH] Digest sent successfully.")
    except Exception as e:
        logger.error(f"[BRAIN_SYNTH] Failed to send digest: {e}")

async def brain_synthesizer_loop(bot_client, target_chat_id: int):
    """Async loop that runs every 6 hours to synthesize data."""
    await asyncio.sleep(180) # Boot delay
    logger.info("[BRAIN_SYNTH] 24/7 Synthesizer loop started.")
    
    while True:
        try:
            await run_brain_synthesizer_cycle(bot_client, target_chat_id)
        except Exception as e:
            logger.error(f"[BRAIN_SYNTH] Error in loop: {e}")
        
        # Har 6 soatda aylanadi (21600 soniya)
        await asyncio.sleep(21600)
