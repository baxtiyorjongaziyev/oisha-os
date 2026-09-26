import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

cmd = [
    "ssh",
    "-i", "C:/Users/baxti/.ssh/oracle_free_tier_ed25519",
    "-o", "StrictHostKeyChecking=no",
    "ubuntu@163.192.10.104",
    """/home/ubuntu/oisha-os/venv/bin/python3 -c "
import sqlite3
conn = sqlite3.connect('/home/ubuntu/oisha-os/data/leadgen_delivery.db')
rows = conn.execute(\\"SELECT rowid, leadgen_id, lead_id, destination, updated_at FROM deliveries WHERE updated_at >= '2026-09-24' ORDER BY rowid ASC;\\").fetchall()
print(f'Total leads today: {len(rows)}')
for r in rows:
    print(r)
" """
]

res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20)
print(res.stdout)
if res.stderr:
    print("STDERR:", res.stderr)
