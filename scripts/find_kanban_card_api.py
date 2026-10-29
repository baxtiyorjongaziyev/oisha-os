import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('scripts/kanban.js', 'r', encoding='utf-8') as f:
    text = f.read()

# search for all calls to e( in kanban.js
# e("..." or e(`/...
matches = set(re.findall(r'\be\([\'"`]([^\'"`]+)[\'"`]', text))
print('API calls in kanban.js:')
for m in sorted(matches):
    print(' ', m)

# Also check for any click handler on card
# search for onCardClick or onClick or setSelectedLead or leadId
card_clicks = [m.start() for m in re.finditer(r'setSelected|selectedLead|openCard|openLead|activeLead', text, re.IGNORECASE)]
print('Card click matches count:', len(card_clicks))
for idx in card_clicks[:5]:
    print('Snippet:', text[max(0, idx-50):min(len(text), idx+150)].replace('\n', ' '))
