import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = 'https://sales.kontaktmarkazi.com/assets/96a52cce0f34b447a4ffec6ae3a3891931057178/shared-DX4eubY-.js'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    content = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
    print(f'Downloaded shared-DX4eubY-.js, size: {len(content)} bytes')
    with open('scripts/shared.js', 'w', encoding='utf-8') as f:
        f.write(content)
except Exception as e:
    print('Failed:', e)
    sys.exit(1)

# Find all api / endpoints / URLs
matches = set(re.findall(r'[\'"`](/api/[^\'"`]+)[\'"`]', content))
print(f'Total /api/ endpoints found: {len(matches)}')
for a in sorted(matches):
    print(' ', a)

# Find any baseUrl or api base
bases = re.findall(r'(?:baseURL|API_URL|VITE_[A-Z_]+)[^;,}]+', content)
print('Bases/Env vars:', bases)
