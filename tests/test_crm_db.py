import asyncio
from database import Database

async def test_crm():
    db = Database("bot_database.db")
    info = db.get_user_info(999111222)
    print("User info:", info)

if __name__ == "__main__":
    asyncio.run(test_crm())
