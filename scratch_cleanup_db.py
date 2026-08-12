import os
from dotenv import load_dotenv
import libsql_client

load_dotenv()

client = libsql_client.create_client_sync(url=os.getenv("TURSO_DATABASE_URL"), auth_token=os.getenv("TURSO_AUTH_TOKEN"))

rs = client.execute("SELECT call_id, transcript FROM call_analyses")
hallucinations = []
for row in rs.rows:
    call_id = row[0]
    transcript = row[1]
    if transcript and len(transcript) < 200 and 'Qandaysiz' in transcript and 'Yaxshi' in transcript and 'Salom' in transcript:
        hallucinations.append(call_id)
    elif transcript and len(transcript) < 200 and 'A: Salom' in transcript and 'B: Salom' in transcript:
        hallucinations.append(call_id)

print(f"Found {len(hallucinations)} hallucinated calls.")
for cid in hallucinations:
    client.execute(f"DELETE FROM call_analyses WHERE call_id = '{cid}'")
    print(f"Deleted call_id {cid}")
