import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from src.database import Database

async def test():
    try:
        db = Database()
        print("DB Initialization: SUCCESS")
        val = await db.get_state("test_key")
        print(f"Database Query: SUCCESS (Value: {val})")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test())
