import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('scripts/bundle.js', 'w', encoding='utf-8') as f:
    pass

import urllib.request
url = 'https://sales.kontaktmarkazi.com/assets/96a52cce0f34b447a4ffec6ae3a3891931057178/index-CmIOYR1t.js'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
content = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
with open('scripts/bundle.js', 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Saved bundle.js, length: {len(content)}')

# Search for fetch / axios calls
fetch_calls = re.findall(r'fetch\([^\)]+\)', content)
print('Fetch calls count:', len(fetch_calls))
for fc in fetch_calls[:10]:
    print(' ', fc[:150])

# Search for keywords like kanban, leads, audio, call, record
for kw in ['kanban', 'leads', 'calls', 'audio', 'export', 'board', 'recording']:
    matches = [m.start() for m in re.finditer(kw, content, re.IGNORECASE)]
    print(f'Keyword "{kw}": {len(matches)} occurrences')
    for idx in matches[:3]:
        snippet = content[max(0, idx-50):min(len(content), idx+100)].replace('\n', ' ')
        print(f'   [{idx}]: {snippet}')
