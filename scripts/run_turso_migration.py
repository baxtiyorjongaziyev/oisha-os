import asyncio
from src.database import Database

async def run():
    db = Database()
    await db.init_db()
    conn = await db.get_connection()
    
    # Try adding the columns to the Turso DB
    try:
        await conn.execute("ALTER TABLE tasks ADD COLUMN profit_estimate INTEGER DEFAULT 0")
        print("Added profit_estimate")
    except Exception as e:
        print(f"Failed profit_estimate: {e}")
        
    try:
        await conn.execute("ALTER TABLE tasks ADD COLUMN source_manager TEXT DEFAULT 'oisha'")
        print("Added source_manager")
    except Exception as e:
        print(f"Failed source_manager: {e}")
        
    try:
        await conn.execute("ALTER TABLE tasks ADD COLUMN external_task_id TEXT")
        print("Added external_task_id")
    except Exception as e:
        print(f"Failed external_task_id: {e}")
        
    try:
        await conn.execute("ALTER TABLE tasks ADD COLUMN is_frog BOOLEAN DEFAULT FALSE")
        print("Added is_frog")
    except Exception as e:
        print(f"Failed is_frog: {e}")
        
    await conn.commit()
    print("Migration complete.")

if __name__ == "__main__":
    asyncio.run(run())
