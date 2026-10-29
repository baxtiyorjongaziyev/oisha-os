import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = 'https://sales.kontaktmarkazi.com/assets/96a52cce0f34b447a4ffec6ae3a3891931057178/index-CmIOYR1t.js'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    content = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
    print(f'Downloaded JS bundle, size: {len(content)} bytes')
except Exception as e:
    print('Failed to download:', e)
    sys.exit(1)

# Find all api endpoints
pattern = r'[\'"`](/api/[^\'"`]+)[\'"`]'
matches = set(re.findall(pattern, content))
print(f'Total endpoints found: {len(matches)}')
for a in sorted(matches):
    print(' ', a)
