import asyncio
import os
from dotenv import load_dotenv
import libsql_client

load_dotenv()

async def run():
    url = os.getenv("TURSO_DATABASE_URL")
    token = os.getenv("TURSO_AUTH_TOKEN")
    if not url or not token:
        print("Missing TURSO env vars")
        return
        
    print(f"Connecting to {url}...")
    client = libsql_client.create_client_sync(url=url, auth_token=token)
    
    commands = [
        "ALTER TABLE tasks ADD COLUMN profit_estimate INTEGER DEFAULT 0",
        "ALTER TABLE tasks ADD COLUMN source_manager TEXT DEFAULT 'oisha'",
        "ALTER TABLE tasks ADD COLUMN external_task_id TEXT",
        "ALTER TABLE tasks ADD COLUMN is_frog BOOLEAN DEFAULT FALSE",
    ]
    
    for cmd in commands:
        try:
            client.execute(cmd)
            print(f"Success: {cmd}")
        except Exception as e:
            print(f"Error for '{cmd}': {e}")

if __name__ == "__main__":
    asyncio.run(run())
