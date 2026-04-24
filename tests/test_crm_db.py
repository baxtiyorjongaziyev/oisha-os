import asyncio
from database import Database

async def test_crm():
    db = Database("bot_database.db")
    try:
        info = await db.get_user_info(999111222)
        print("User info:", info)
        assert info is None or isinstance(info, dict)
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(test_crm())
