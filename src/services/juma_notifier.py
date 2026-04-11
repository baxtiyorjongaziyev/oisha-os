import asyncio
import logging
from datetime import datetime, time
from telethon import TelegramClient, functions, types
from src.database import Database
from src.settings import settings

logger = logging.getLogger(__name__)

class JumaNotifier:
    """Automated Friday Greetings for TN5 Classmates."""

    def __init__(self, client: TelegramClient, db: Database, group_id: int = None):
        self.client = client
        self.db = db
        self.group_id = group_id # Default primary group
        self.RUN_WINDOW_START = time(8, 0)   # 08:00 AM
        self.RUN_WINDOW_END = time(21, 0)    # 09:00 PM

    async def check_and_send(self):
        """Check if it's Friday morning and we haven't sent greetings yet."""
        now = datetime.now()
        
        # 1. Check if it's Friday (ISO weekday 5)
        if now.weekday() != 4: # 0=Monday, 4=Friday
            return

        # 2. Check if we are in the time window (8 AM - 11 AM)
        if not (self.RUN_WINDOW_START <= now.time() <= self.RUN_WINDOW_END):
            return

        # 3. Check if already sent today
        today_str = now.strftime('%Y-%m-%d')
        if await self._is_already_sent(today_str):
            logger.info(f"👸 [JUMA] Greetings already sent for {today_str}. Skipping.")
            return

        # 4. START GREETINGS
        logger.info(f"👸 [JUMA] Friday Morning! Sending greetings to TN5 classmates...")
        await self.send_greetings(today_str)

    async def _is_already_sent(self, date_str: str) -> bool:
        """Check the database for previous runs of this job."""
        try:
            return await self.db.is_job_run('juma_mubarak', date_str)
        except Exception as e:
            logger.error(f"[JUMA DB ERROR] check: {e}")
            return False

    async def _mark_as_sent(self, date_str: str):
        """Record the successful run in the database."""
        try:
            await self.db.mark_job_run('juma_mubarak', date_str)
        except Exception as e:
            logger.error(f"[JUMA DB ERROR] mark: {e}")

    async def get_tn5_classmates(self):
        """Fetch all users identified as TN5 students from the database."""
        classmates = []
        try:
            conn = await self.db.get_connection()
            # Filter by last_name suffix or specific TN5 mentions
            query = """
                SELECT user_id, first_name, username 
                FROM users 
                WHERE last_name LIKE '%TN%' 
                   OR last_name LIKE '%TEZ%'
                   OR intent = 'TN5_CLASSMATE' 
            """
            async with conn.execute(query) as cursor:
                rows = await cursor.fetchall()
                for r in rows:
                    classmates.append({"id": r[0], "name": r[1], "username": r[2]})
        except Exception as e:
            logger.error(f"[JUMA DB ERROR] fetch: {e}")
        
        # 2. CACHED GROUP DISCOVERY (TNx) - Bypassing get_dialogs due to flood wait
        logger.info("👸 [JUMA] Using hardcoded Group IDs to bypass flood wait...")
        # [GOD MODE] Hardcoded IDs for TN2, TN3, TN4, TN5 (pre-verified or fallback)
        target_group_ids = [
            -1002061483832, # TN5 Juma Group
            -1001820339529, # TN5 Primary
            -1002222333444, # Placeholder for TN4 (bot will discover naturally later)
            -1001111222333  # Placeholder for TN3 (bot will discover naturally later)
        ]
        if self.group_id and self.group_id not in target_group_ids:
            target_group_ids.append(self.group_id)
        
        # Original dynamic logic (commented out to avoid flood waits)
        """
        try:
            dialogs = await self.client.get_dialogs()
            for d in dialogs:
                # ...
        except: pass
        """

        # 3. CRAWL ALL IDENTIFIED GROUPS & DEDUPLICATE
        processed_ids = {c['id'] for c in classmates} # Start with DB classmates
        logger.info(f"👸 [JUMA] Starting with {len(classmates)} classmates from DB. Crawling groups for more...")
        
        for g_id in target_group_ids:
            try:
                # [GOD MODE] Use a shorter timeout or check for flood wait
                participants = await self.client.get_participants(g_id, limit=200)
                for u in participants:
                    if u.bot or u.is_self: continue
                    if u.id in processed_ids: continue # DEDUPLICATION
                    
                    # [GOD MODE] STRICT FAMILY/PERSONAL EXCLUSION
                    full_name = f"{u.first_name or ''} {u.last_name or ''}".strip()
                    if any(excl.lower() in full_name.lower() for excl in settings.EXCLUDED_NAMES):
                        continue

                    classmates.append({
                        "id": u.id, 
                        "name": u.first_name or "Do'stim", 
                        "username": u.username
                    })
                    processed_ids.add(u.id)
            except Exception as e:
                logger.error(f"👸 [JUMA] Group {g_id} crawl error (likely flood wait): {e}")

        return classmates

    async def send_greetings(self, date_str: str):
        """Perform mass messaging with random delays."""
        classmates = await self.get_tn5_classmates()
        
        if not classmates:
            logger.warning("👸 [JUMA] No TN5 classmates found in database!")
            # Still mark as sent to avoid repeated empty checks
            await self._mark_as_sent(date_str)
            return

        logger.info(f"👸 [JUMA] Found {len(classmates)} classmates. Delivery started...")
        
        success_count = 0
        for peer in classmates:
            try:
                # 1. CHECK IF ALREADY SENT TO THIS INDIVIDUAL TODAY
                conn = await self.db.get_connection()
                query = "SELECT 1 FROM juma_sent_logs WHERE user_id = ? AND run_date = ?"
                async with conn.execute(query, (peer['id'], date_str)) as cursor:
                    if await cursor.fetchone():
                        logger.debug(f"👸 [JUMA SKIP] Already sent to {peer['id']} today.")
                        continue

                # 2. SAVE AS CONTACT FIRST (Safer for outreach)
                contact_name = f"TN5 Gr {peer['name']}"
                try:
                    await self.client(functions.contacts.AddContactRequest(
                        id=peer['id'],
                        first_name=contact_name,
                        last_name="",
                        phone="",  # Phone is optional when adding by ID
                        add_phone_privacy_exception=True
                    ))
                    logger.debug(f"👤 [JUMA] Saved {peer['id']} as '{contact_name}'")
                except Exception as ce:
                    logger.warning(f"👤 [JUMA] Could not save contact {peer['id']}: {ce}")

                # 3. Final Greeting Template (User Specified Exact Text)
                message = (
                    "Assalomu alaykum\n"
                    "Juma ayyomingiz muborak bo'lsin.\n"
                    "Jumaning xayru barokati sizga bo'lsin."
                )
                
                # 4. SEND via Userbot (Personal account)
                await self.client.send_message(peer['id'], message)
                
                # 5. LOG SUCCESS PERSISTENTLY
                await conn.execute("INSERT INTO juma_sent_logs (user_id, run_date) VALUES (?, ?)", (peer['id'], date_str))
                await conn.commit()

                success_count += 1
                logger.info(f"✅ [JUMA] Sent to {peer['name']} ({peer['id']})")
                
                # 6. ULTRA-SAFE EVENING DELAY: 120-300 seconds random delay
                wait_time = random.uniform(120, 300)
                await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"❌ [JUMA ERROR] Failed to send to {peer['id']}: {e}")
                # Wait longer on error to avoid further flags
                await asyncio.sleep(60)

        # 4. Finalize
        await self._mark_as_sent(date_str)
        logger.info(f"👸 [JUMA] Success! Sent {success_count} greetings for {date_str}.")

import random
