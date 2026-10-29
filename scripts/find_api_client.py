import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('scripts/bundle.js', 'r', encoding='utf-8') as f:
    bundle = f.read()

# Search for "/calls" or "Bearer " or api client setup
matches = [m.start() for m in re.finditer(r'/calls|awp_token|baseURL|Authorization', bundle, re.IGNORECASE)]
print(f'Matches count: {len(matches)}')
for idx in matches[:10]:
    snippet = bundle[max(0, idx-60):min(len(bundle), idx+100)].replace('\n', ' ')
    print(f'[{idx}]: {snippet}')
