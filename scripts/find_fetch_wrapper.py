import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('scripts/shared.js', 'r', encoding='utf-8') as f:
    text = f.read()

# Search for Le definition or export
matches = [m.start() for m in re.finditer(r'\b(?:const|let|var|function)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>|function\s+([a-zA-Z0-9_$]+)\s*\(', text)]
print(f'Total functions in shared.js: {len(matches)}')

# Let's search for "api" or fetch wrapper in shared.js
# Look for where localStorage.getItem("awp_token") or headers are used
token_matches = [m.start() for m in re.finditer(r'awp_token', text)]
print('awp_token occurrences in shared.js:', len(token_matches))
for idx in token_matches:
    print('---')
    print(text[max(0, idx-100):min(len(text), idx+200)].replace('\n', ' '))
