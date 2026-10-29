import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('scripts/kanban.js', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('Xs,{call:')
print(text[idx-1200:idx])
