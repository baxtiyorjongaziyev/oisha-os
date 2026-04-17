import asyncio
import logging
import datetime
from src.database import Database
from src.services.core.wow_service_engine import WowServiceEngine
from src import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_wow_engine():
    db = Database()
    await db.init_instance()
    
    # Mock bot client
    class MockBot:
        async def send_message(self, chat_id, text, **kwargs):
            logger.info(f"📨 [MOCK BOT] Sent to {chat_id}: \n{text}")

    engine = WowServiceEngine(db, bot_client=MockBot())
    
    # 1. Simulate a project from Airtable (Mocking return values)
    # Since we can't easily mock AirtableSync internally without monkeypatching,
    # we'll test the _audit_project_journey logic by manually calling it with a dict.
    
    test_project = {
        'id': 'recTEST123',
        'fields': {
            'Loyihani nomi?': 'Test Wow Project',
            'Loyiha bosqichi': 'Briefing / Research',
            'PM': 'Inomjon aka'
        }
    }
    
    logger.info("Running audit on test project (Briefing stage)...")
    
    # First time: it should just CREATE the checkpoint record
    await engine._audit_project_journey(test_project)
    
    # Check DB
    cp = await db.get_checkpoint('recTEST123', 'project_kickoff_recap')
    if cp:
        logger.info(f"✅ Checkpoint created: {cp}")
    else:
        logger.error("❌ Checkpoint NOT created!")

    # Second time (immediate): it should NOT trigger because delay_hours=24
    await engine._audit_project_journey(test_project)
    
    # Simulate time passed (manually update created_at in DB)
    conn = await db.get_connection()
    past_date = (datetime.datetime.now() - datetime.timedelta(hours=25)).isoformat()
    await conn.execute("UPDATE service_checkpoints SET created_at = ? WHERE external_id = ?", (past_date, 'recTEST123'))
    await conn.commit()
    
    logger.info("Running audit after 25 hours simulation...")
    # This should trigger the message
    await engine._audit_project_journey(test_project)

if __name__ == "__main__":
    asyncio.run(test_wow_engine())
