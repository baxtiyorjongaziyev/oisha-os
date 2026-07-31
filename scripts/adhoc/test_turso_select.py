import asyncio
import os
from dotenv import load_dotenv
import libsql_client

load_dotenv()

async def run():
    url = os.getenv("TURSO_DATABASE_URL")
    token = os.getenv("TURSO_AUTH_TOKEN")
    
    print(f"Connecting to {url}...")
    client = libsql_client.create_client_sync(url=url, auth_token=token)
    
    try:
        rs = client.execute("SELECT * FROM tasks LIMIT 1")
        print("tasks columns:", [c[0] for c in rs.columns])
    except Exception as e:
        print(f"tasks error: {e}")
        
    try:
        rs = client.execute("SELECT * FROM users LIMIT 1")
        print("users columns:", [c[0] for c in rs.columns])
    except Exception as e:
        print(f"users error: {e}")
        
if __name__ == "__main__":
    asyncio.run(run())
