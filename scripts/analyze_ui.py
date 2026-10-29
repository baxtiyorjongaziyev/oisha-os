import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = 'https://sales.kontaktmarkazi.com/assets/96a52cce0f34b447a4ffec6ae3a3891931057178/shared-ui-DsoKWx3n.js'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
content = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
print('Downloaded shared-ui, size:', len(content))

# search for /file or recording or audio
matches = set(re.findall(r'[\'"`]([^\'"`]*(?:record|audio|file|play|stream)[^\'"`]*)[\'"`]', content, re.IGNORECASE))
for m in sorted(matches):
    if len(m) < 80:
        print(' ', m)
