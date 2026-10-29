import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

for fn in ['scripts/kanban.js', 'scripts/bundle.js']:
    with open(fn, 'r', encoding='utf-8') as f:
        text = f.read()
    # Search for audio url or recording playback logic
    idx = text.find('recordingId')
    while idx != -1:
        snippet = text[max(0, idx-100):min(len(text), idx+300)].replace('\n', ' ')
        print(f'{fn} [{idx}]: {snippet}')
        idx = text.find('recordingId', idx+1)
