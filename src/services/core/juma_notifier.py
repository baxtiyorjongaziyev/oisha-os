import asyncio
import random
import logging
import os
from datetime import datetime, time
from telethon import TelegramClient, functions
from src.database import Database
from src.settings import settings
from src.services.core.customer_outbound_policy import (
    automatic_customer_send_allowed,
    build_humanized_juma_greeting,
)

logger = logging.getLogger(__name__)


class JumaNotifier:
    """Automated Friday Greetings for TN5 Classmates."""

    def __init__(self, client: TelegramClient, db: Database, group_id: int = None):
        self.client = client
        self.db = db
        self.group_id = group_id  # Default primary group
        self.RUN_WINDOW_START = time(0, 0)  # 00:00 AM
        self.RUN_WINDOW_END = time(23, 59)  # 11:59 PM

    async def check_and_send(self):
        """Check if it's Friday morning and we haven't sent greetings yet."""
        if os.getenv("ENABLE_JUMA_NOTIFIER", "").strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            logger.info(
                "[JUMA] Auto mass greeting is disabled. Set ENABLE_JUMA_NOTIFIER=1 to enable."
            )
            return

        now = datetime.now()

        # Owner-approved sole exception to the automatic-customer-message ban.
        if not automatic_customer_send_allowed("juma", now=now):
            return

        # 2. Check if we are in the time window (8 AM - 11 AM)
        if not (self.RUN_WINDOW_START <= now.time() <= self.RUN_WINDOW_END):
            return

        # 3. Check if already sent today
        today_str = now.strftime("%Y-%m-%d")
        if await self._is_already_sent(today_str):
            logger.info(f"👸 [JUMA] Greetings already sent for {today_str}. Skipping.")
            return

        logger.info("[JUMA] Sending this week's short, humanized greeting.")
        await self.send_greetings(today_str)

    async def _is_already_sent(self, date_str: str) -> bool:
        """Check the database for previous runs of this job."""
        try:
            return await self.db.is_job_run("juma_mubarak", date_str)
        except Exception as e:
            logger.error(f"[JUMA DB ERROR] check: {e}")
            return False

    async def _mark_as_sent(self, date_str: str):
        """Record the successful run in the database."""
        try:
            await self.db.mark_job_run("juma_mubarak", date_str)
        except Exception as e:
            logger.error(f"[JUMA DB ERROR] mark: {e}")

    async def get_tn5_classmates(self):
        """Fetch all users identified as TN5 students from the database."""
        classmates = []
        try:
            conn = await self.db.get_connection()
            # Filter by last_name suffix or specific TN mentions (2, 3, 4, 5)
            query = """
                SELECT user_id, first_name, username 
                FROM users 
                WHERE (last_name LIKE '%TN%' OR first_name LIKE '%TN%' OR contact_name LIKE '%TN%')
                   OR (last_name LIKE '%Tez Natija%' OR first_name LIKE '%Tez Natija%')
            """
            async with conn.execute(query) as cursor:
                rows = await cursor.fetchall()
                for r in rows:
                    classmates.append({"id": r[0], "name": r[1], "username": r[2]})
        except Exception as e:
            logger.error(f"[JUMA DB ERROR] fetch: {e}")

        # 2. CACHED GROUP DISCOVERY (TNx)
        logger.info("👸 [JUMA] Targeting TN2, TN3, TN4, and TN5 groups...")
        target_group_ids = [
            -1002061483832,  # TN5 Juma Group
            -1001820339529,  # TN5 Primary
            -1002167483921,  # TN4 Placeholder
            -1001928374655,  # TN3 Placeholder
            -1001827364554,  # TN2 Placeholder
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
        processed_ids = {c["id"] for c in classmates}  # Start with DB classmates
        logger.info(
            f"👸 [JUMA] Starting with {len(classmates)} classmates from DB. Crawling groups for more..."
        )

        for g_id in target_group_ids:
            try:
                # [GOD MODE] Use a shorter timeout or check for flood wait
                participants = await self.client.get_participants(g_id, limit=200)
                for u in participants:
                    if u.bot or u.is_self:
                        continue
                    if u.id in processed_ids:
                        continue  # DEDUPLICATION

                    # [GOD MODE] STRICT FAMILY/PERSONAL EXCLUSION
                    full_name = f"{u.first_name or ''} {u.last_name or ''}".strip()
                    if any(
                        excl.lower() in full_name.lower()
                        for excl in settings.EXCLUDED_NAMES
                    ):
                        continue

                    classmates.append(
                        {
                            "id": u.id,
                            "name": u.first_name or "Do'stim",
                            "username": u.username,
                        }
                    )
                    processed_ids.add(u.id)
            except Exception as e:
                logger.error(
                    f"👸 [JUMA] Group {g_id} crawl error (likely flood wait): {e}"
                )

        return classmates

    async def send_greetings(self, date_str: str, source_message=None):
        """Perform mass messaging with random delays."""
        if not automatic_customer_send_allowed("juma"):
            logger.warning("[JUMA] Direct send blocked outside Friday.")
            return

        classmates = await self.get_tn5_classmates()

        if not classmates:
            logger.warning("👸 [JUMA] No classmates found in database!")
            await self._mark_as_sent(date_str)
            return

        logger.info(
            f"👸 [JUMA] Found {len(classmates)} classmates. Delivery started..."
        )

        success_count = 0
        for peer in classmates:
            try:
                # 1. CHECK IF ALREADY SENT
                conn = await self.db.get_connection()
                query = (
                    "SELECT 1 FROM juma_sent_logs WHERE user_id = ? AND run_date = ?"
                )
                async with conn.execute(query, (peer["id"], date_str)) as cursor:
                    if await cursor.fetchone():
                        continue

                # 2. SAVE AS CONTACT
                contact_name = f"TN Gr {peer['name']}"
                try:
                    await self.client(
                        functions.contacts.AddContactRequest(
                            id=peer["id"],
                            first_name=contact_name,
                            last_name="",
                            phone="",
                            add_phone_privacy_exception=True,
                        )
                    )
                except Exception:
                    logger.error("Exception handled in %s", __name__, exc_info=True)

                # 3. SEND
                message = build_humanized_juma_greeting(peer["name"])
                await self.client.send_message(peer["id"], message)

                # 4. LOG SUCCESS
                await conn.execute(
                    "INSERT INTO juma_sent_logs (user_id, run_date) VALUES (?, ?)",
                    (peer["id"], date_str),
                )
                await conn.commit()

                success_count += 1
                logger.info(f"✅ [JUMA] Sent to {peer['name']}")

                # SAFE DELAY
                await asyncio.sleep(random.uniform(120, 240))

            except Exception as e:
                logger.error(f"❌ [JUMA ERROR] {peer['id']}: {e}")
                if "flood wait" in str(e).lower():
                    await asyncio.sleep(600)  # Wait 10 mins on flood
                else:
                    await asyncio.sleep(60)

        # 4. Finalize
        await self._mark_as_sent(date_str)
        logger.info(
            f"👸 [JUMA] Success! Sent {success_count} greetings for {date_str}."
        )
