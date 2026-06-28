"""Scheduler for Daily Frog briefing."""
import asyncio
import logging
from src.database import get_db
from src.services.ai.frog_agent import FrogAgent

logger = logging.getLogger(__name__)

async def send_daily_frog_brief(client=None, team_group_id=None):
    """Fetches tasks, finds the frog, and sends to team group."""
    logger.info("[FROG] Starting daily frog identification...")
    db = get_db()
    
    # Get all pending tasks
    # Wait, get_overdue_tasks only returns overdue tasks. We need all pending tasks.
    conn = await db.get_connection()
    async with conn.execute(
        "SELECT id, title, description, priority, profit_estimate FROM tasks WHERE status='Pending'"
    ) as cursor:
        rows = await cursor.fetchall()
        
    if not rows:
        logger.info("[FROG] No pending tasks found.")
        return
        
    tasks = [
        {
            "id": r[0],
            "title": r[1],
            "description": r[2],
            "priority": r[3],
            "profit_estimate": r[4] or 0
        } for r in rows
    ]
    
    agent = FrogAgent()
    frog = await agent.identify_frog(tasks)
    if not frog:
        logger.error("[FROG] Agent failed to identify a frog.")
        return
        
    logger.info(f"[FROG] Found frog task {frog.most_important_task_id}. Estimate: ${frog.profit_estimate}")
    
    # Mark as frog in DB
    await conn.execute("UPDATE tasks SET is_frog=0") # reset old frogs
    await conn.execute("UPDATE tasks SET is_frog=1 WHERE id=?", (frog.most_important_task_id,))
    await conn.commit()
    
    # Send message via Telegram
    if client and team_group_id:
        try:
            await client.send_message(
                team_group_id,
                f"🐸 <b>Qurbaqani yeymiz!</b>\n\n{frog.motivation_message}\n\n"
                f"<i>Daromad prognozi: ${frog.profit_estimate}</i>",
                parse_mode="html"
            )
        except Exception as e:
            logger.error(f"[FROG] Failed to send telegram message: {e}")

async def daily_frog_loop(client, team_group_id):
    """Async loop that runs every minute and triggers at 09:00."""
    from src.time_utils import get_local_now
    await asyncio.sleep(10)
    logger.info("[FROG] Daily frog loop started.")
    last_run_date = None
    
    while True:
        try:
            now = get_local_now()
            today_str = now.strftime("%Y-%m-%d")
            if now.hour == 9 and now.minute == 0 and last_run_date != today_str:
                await send_daily_frog_brief(client, team_group_id)
                last_run_date = today_str
        except Exception as e:
            logger.error(f"[FROG] Error in loop: {e}")
        await asyncio.sleep(30)
