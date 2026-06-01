import asyncio
import random
import logging
import os
from datetime import datetime, time
from telethon import TelegramClient, functions
from src.database import Database
from src.settings import settings

logger = logging.getLogger(__name__)


class JumaNotifier:
    """Automated Friday Greetings for TN5 Classmates."""

    def __init__(self, client: TelegramClient, db: Database, group_id: int = None):
        self.client = client
        self.db = db
        self.group_id = group_id  # Default primary group
        self.RUN_WINDOW_START = time(0, 0)  # 00:00 AM
        self.RUN_WINDOW_END = time(23, 59)  # 11:59 PM

        # AI Config
        from google import genai

        self.genai_client = genai.Client(
            api_key=settings.GEMINI_API_KEY.get_secret_value()
        )
        self.model_name = os.getenv("GEMINI_JUMA_MODEL", settings.GEMINI_CALL_MODEL)

    async def is_juma_greeting(self, text: str) -> bool:
        """Use Gemini to detect if the text is a Juma greeting."""
        if not text:
            return False

        prompt = (
            "Determine if the following text is a Juma (Friday) greeting/blessing in Uzbek. "
            "Respond with only 'YES' or 'NO'.\n\n"
            f"Text: {text}"
        )
        try:
            from src.main import safe_ai_call

            response = await safe_ai_call(
                client=self.genai_client, prompt=prompt, model=self.model_name
            )
            return "YES" in (response.text or "").upper()
        except Exception as e:
            logger.error(f"[JUMA AI] Detection error: {e}")
            # Fallback to simple keyword check
            keywords = ["juma", "muborak", "ayyom", "natidja"]
            return any(k in text.lower() for k in keywords)

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

        # 1. Check if it's Friday (ISO weekday 5)
        if now.weekday() != 4:  # 0=Monday, 4=Friday
            return

        # 2. Check if we are in the time window (8 AM - 11 AM)
        if not (self.RUN_WINDOW_START <= now.time() <= self.RUN_WINDOW_END):
            return

        # 3. Check if already sent today
        today_str = now.strftime("%Y-%m-%d")
        if await self._is_already_sent(today_str):
            logger.info(f"👸 [JUMA] Greetings already sent for {today_str}. Skipping.")
            return

        # 4. SEARCH FOR CHANNEL GREETING (Smarter auto-outreach)
        logger.info(
            "👸 [JUMA] Friday Morning! Searching channel for a greeting to forward..."
        )
        try:
            # Check last 3 messages in channel
            async for msg in self.client.iter_messages("baxtiyorjongaziyev", limit=3):
                if await self.is_juma_greeting(msg.text):
                    logger.info(
                        f"👸 [JUMA] Found greeting in channel (msg {msg.id}). Forwarding..."
                    )
                    await self.send_greetings(today_str, source_message=msg)
                    return
        except Exception as se:
            logger.error(f"[JUMA SEARCH ERROR] {se}")

        # 5. FALLBACK: Send default personalized message
        logger.info(
            "👸 [JUMA] No channel greeting found. Sending default personalized messages..."
        )
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
                except:
                    pass

                # 3. SEND
                if source_message:
                    # Forward from channel
                    await self.client.forward_messages(peer["id"], source_message)
                else:
                    # Default Template
                    message = (
                        f"Assalomu alaykum, qadrli kursdoshim {peer['name']}!\n\n"
                        "Juma ayyomingiz muborak bo'lsin. Alloh taolo bugungi muborak kunda ishlaringizga baraka, "
                        "oilangizga xotirjamlik, qalbingizga nur va biznesingizga halol o'sish bersin.\n\n"
                        "Har birimiz boshlagan ishimizda chiroyli natija, manfaatli hamkorlik va kuchli iymon bilan oldinga yuraylik. "
                        "Sizga fayzli juma, barakali kun va katta-katta yutuqlar tilayman."
                    )
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
