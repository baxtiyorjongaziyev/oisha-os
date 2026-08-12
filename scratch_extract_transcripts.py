import os
from dotenv import load_dotenv
import libsql_client

load_dotenv()
client = libsql_client.create_client_sync(url=os.getenv("TURSO_DATABASE_URL"), auth_token=os.getenv("TURSO_AUTH_TOKEN"))

rs = client.execute("SELECT call_id, transcript FROM call_analyses WHERE transcript IS NOT NULL AND transcript != '' ORDER BY created_at DESC LIMIT 30")

count = 0
with open("transcripts_utf8.txt", "w", encoding="utf-8") as f:
    for row in rs.rows:
        call_id, transcript = row[0], row[1]
        if len(transcript) > 200:
            f.write(f"--- CALL ID {call_id} ---\n")
            f.write(transcript.strip() + "\n\n")
            count += 1
            if count >= 10:
                break
