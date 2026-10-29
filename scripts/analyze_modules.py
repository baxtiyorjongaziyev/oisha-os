import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

base = 'https://sales.kontaktmarkazi.com/assets/96a52cce0f34b447a4ffec6ae3a3891931057178/'
modules = [
    'Kanban-DTZZHtNb.js',
    'Calls-BgriyvX_.js',
    'RecordingStorage-DX1ZFkwH.js',
    'AiAnalysis-CNGSph9g.js'
]

for mod in modules:
    url = base + mod
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        content = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
        print(f'=== {mod} (size {len(content)}) ===')
        # find endpoints / URLs / API calls
        apis = set(re.findall(r'[\'"`]([^\'"`]*(?:api|lead|call|recording|audio|kanban|voice)[^\'"`]*)[\'"`]', content, re.IGNORECASE))
        for a in sorted(apis):
            if any(k in a for k in ['/api', '/call', '/lead', '/rec', '/voice', 'http']):
                if len(a) < 100:
                    print('  api:', a)
    except Exception as e:
        print(f'Failed {mod}:', e)
