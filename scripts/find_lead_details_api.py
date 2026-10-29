import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

files = [
    'scripts/bundle.js',
    'scripts/shared.js'
]

# also download Kanban-DTZZHtNb.js to scripts/kanban.js if not done
import urllib.request
url = 'https://sales.kontaktmarkazi.com/assets/96a52cce0f34b447a4ffec6ae3a3891931057178/Kanban-DTZZHtNb.js'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    content = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
    with open('scripts/kanban.js', 'w', encoding='utf-8') as f:
        f.write(content)
    files.append('scripts/kanban.js')
except Exception as e:
    pass

for fn in files:
    with open(fn, 'r', encoding='utf-8') as f:
        text = f.read()
    # Search for endpoint that fetches a single lead or its card
    # e.g. /leads/${ or /leads/
    matches = set(re.findall(r'[\'"`](/leads/[^\'"`]+)[\'"`]', text))
    print(f'=== {fn} /leads/ matches ===')
    for m in sorted(matches):
        print(' ', m)
    # Search for where recordingId or s.recordingId or .recording is used
    rec_matches = [m.start() for m in re.finditer(r'recordingId', text)]
    print(f'recordingId matches in {fn}: {len(rec_matches)}')
    for idx in rec_matches[:3]:
        print('  rec snippet:', text[max(0, idx-50):min(len(text), idx+150)].replace('\n', ' '))
