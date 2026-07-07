import asyncio
import json
import os
import sys

sys.path.insert(0, '/home/ubuntu/oisha-os')
os.chdir('/home/ubuntu/oisha-os')

from src.database import get_db

async def run():
    db = get_db()
    conn = await db.get_connection()
    cur = await conn.execute(
        "SELECT call_id, lead_id, transcript, audio_url, analyzed_at FROM call_analyses WHERE transcript LIKE '%Jalolov%'"
    )
    rows = await cur.fetchall()
    
    # We want to format the result nicely
    results = []
    for r in rows:
        results.append({
            "call_id": r[0],
            "lead_id": r[1],
            "transcript": r[2],
            "audio_url": r[3],
            "analyzed_at": r[4]
        })
    print(json.dumps(results, indent=2))

asyncio.run(run())
