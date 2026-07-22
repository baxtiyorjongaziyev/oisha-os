"""Scheduler for Daily Frog briefing."""
import asyncio
import logging
from src.database import get_db
from src.services.ai.frog_agent import FrogAgent

logger = logging.getLogger(__name__)

async def send_daily_frog_brief(bot_client=None, team_group_id=None):
    """Fetches tasks, finds the frog, and sends to team group.

    The brief is delivered by the @jonairobot bot (``bot_client``), never the
    userbot — the morning motivational message must come from the bot account.
    """
    logger.info("[FROG] Starting daily frog identification...")
    from src.settings import settings
    from src.services.core.composio_tasks import ComposioTaskService
    
    db = get_db()
    conn = await db.get_connection()

    if getattr(settings, "FROG_SOURCE", "db") == "composio":
        logger.info("[FROG] Fetching tasks from Composio...")
        composio_service = ComposioTaskService()
        fetched_tasks = await composio_service.fetch_tasks()
        if fetched_tasks:
            for t in fetched_tasks:
                cur = await conn.execute("SELECT id FROM tasks WHERE external_task_id=?", (t["external_task_id"],))
                row = await cur.fetchone()
                if row:
                    await conn.execute(
                        "UPDATE tasks SET title=?, description=?, priority=?, profit_estimate=?, status='Pending' WHERE id=?",
                        (t["title"], t["description"], t["priority"], t["profit_estimate"], row[0])
                    )
                else:
                    await conn.execute(
                        "INSERT INTO tasks (title, description, priority, profit_estimate, external_task_id, source_manager, status) VALUES (?, ?, ?, ?, ?, ?, 'Pending')",
                        (t["title"], t["description"], t["priority"], t["profit_estimate"], t["external_task_id"], t["source_manager"])
                    )
            await conn.commit()
            logger.info(f"[FROG] Synced {len(fetched_tasks)} tasks from Composio to DB.")
        else:
            logger.warning("[FROG] No tasks fetched from Composio.")

    # Get all pending tasks
    cursor = await conn.execute(
        "SELECT id, title, description, priority, profit_estimate FROM tasks WHERE status='Pending'"
    )
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

    # Ground the numbers on the REAL source task, never the LLM's guess.
    # The LLM only picks which task is the frog + writes the motivation text;
    # profit_estimate must come from the actual Trello/Google Task data.
    selected = next(
        (t for t in tasks if t["id"] == frog.most_important_task_id), None
    )
    if selected is None:
        logger.error(
            "[FROG] LLM returned unknown task id %s — not in source tasks; aborting.",
            frog.most_important_task_id,
        )
        return
    frog.profit_estimate = selected["profit_estimate"] or 0

    logger.info(f"[FROG] Found frog task {frog.most_important_task_id} ({selected['title']}). Real estimate: ${frog.profit_estimate}")
    
    # Mark as frog in DB
    await conn.execute("UPDATE tasks SET is_frog=0") # reset old frogs
    await conn.execute("UPDATE tasks SET is_frog=1 WHERE id=?", (frog.most_important_task_id,))
    await conn.commit()
    
    # Send message via Telegram — only through @jonairobot (bot_client),
    # never the userbot.
    if bot_client and team_group_id:
        try:
            await bot_client.send_message(
                team_group_id,
                f"🐸 <b>Qurbaqani yeymiz!</b>\n\n{frog.motivation_message}\n\n"
                f"<i>Daromad prognozi: ${frog.profit_estimate}</i>",
                parse_mode="html"
            )
        except Exception as e:
            logger.error(f"[FROG] Failed to send telegram message: {e}")

async def daily_frog_loop(bot_client, team_group_id):
    """Async loop that runs every minute and triggers at 09:00.

    ``bot_client`` is the @jonairobot bot client — the brief is always sent
    from the bot account, not the userbot.
    """
    from src.time_utils import get_local_now
    await asyncio.sleep(10)
    logger.info("[FROG] Daily frog loop started.")
    last_run_date = None

    while True:
        try:
            now = get_local_now()
            today_str = now.strftime("%Y-%m-%d")
            if now.hour == 9 and now.minute == 0 and last_run_date != today_str:
                await send_daily_frog_brief(bot_client, team_group_id)
                last_run_date = today_str
        except Exception as e:
            logger.error(f"[FROG] Error in loop: {e}")
        await asyncio.sleep(30)
