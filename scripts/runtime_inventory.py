"""Read-only source inventory. Never inspect environment or credentials."""
import hashlib
import json
from pathlib import Path

root = Path('/home/ubuntu/oisha-os')
files = [
    'src/bootstrap/orchestration/schedulers.py',
    'src/schedulers/remote_staff_checkin_scheduler.py',
    'src/services/core/checkin_composer.py',
    'src/services/core/ai/hermes_provider.py',
    'src/services/core/ai/hermes_harness.py',
    'src/handlers/group_mention.py',
    'scripts/hourly_sales_control.py',
    'scripts/daily_sales_calls_report.py',
]
for name in files:
    path = root / name
    if not path.exists():
        print(json.dumps({'path': name, 'exists': False}))
        continue
    data = path.read_bytes()
    lines = data.decode(errors='replace').splitlines()
    sends = [i for i, s in enumerate(lines, 1) if any(x in s for x in ('send_message(', '.reply(', 'send_telegram(', 'send_once('))]
    print(json.dumps({'path': name, 'exists': True, 'sha256': hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest(), 'send_lines': sends}))
path = root / 'src/bootstrap/orchestration/schedulers.py'
print('SCHEDULER_BOOTSTRAP')
print(path.read_text())
