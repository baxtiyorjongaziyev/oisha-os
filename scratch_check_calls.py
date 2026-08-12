import os
from dotenv import load_dotenv
import libsql_client

load_dotenv()

url = os.getenv("TURSO_DATABASE_URL")
token = os.getenv("TURSO_AUTH_TOKEN")

client = libsql_client.create_client_sync(url=url, auth_token=token)

rs = client.execute("SELECT call_id, audio_url FROM call_analyses ORDER BY created_at DESC LIMIT 5")
for row in rs.rows:
    print(f"Call {row[0]} | URL {row[1]}")
