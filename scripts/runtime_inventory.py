"""Read-only source inventory. Never inspect environment or credentials."""
import hashlib
import json
import ast
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

inventory = {'files': [], 'senders': [], 'schedulers': [], 'memory_files': []}
for folder in ('src', 'scripts'):
    for path in sorted((root / folder).rglob('*.py')):
        if '__pycache__' in path.parts:
            continue
        data = path.read_bytes()
        relative = str(path.relative_to(root))
        inventory['files'].append({'path': relative, 'sha256': hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()})
        try:
            tree = ast.parse(data.decode('utf-8-sig'))
        except (SyntaxError, UnicodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = ast.unparse(node.func)
                if name.endswith(('.send_message', '.reply', '.send_file', '.send_photo', '.send_document')) or name.endswith(('send_telegram', 'send_once')):
                    inventory['senders'].append({'path': relative, 'line': node.lineno, 'call': name})
                if name.endswith(('create_task', 'add_job', 'add_task')):
                    inventory['schedulers'].append({'path': relative, 'line': node.lineno, 'call': name})
for base in (root / 'data', Path('/home/hermes/.hermes')):
    for pattern in ('*.db', '*memory*.json', '*context*.json'):
        for path in base.glob(pattern):
            inventory['memory_files'].append(str(path))
Path('/tmp/oisha-runtime-inventory.json').write_text(json.dumps(inventory, indent=2))
print('INVENTORY_COUNTS', {k: len(v) for k, v in inventory.items()})
