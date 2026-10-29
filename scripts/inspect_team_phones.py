import os
import re

vault = r"C:\Users\baxti\Documents\JonBranding Second Brain"
for root, _, files in os.walk(vault):
    for f in files:
        if f.endswith('.md'):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                lines = fp.readlines()
            for idx, line in enumerate(lines):
                if any(k in line.lower() for k in ['shahnoza', 'rayxona', 'mumtoz', 'baxtiyorjon', 'farangiz', 'oydin']):
                    if re.search(r'\+?998\s?\d{2}\s?\d{3}', line) or 'telefon' in line.lower() or 'raqam' in line.lower():
                        print(f"{f}:{idx+1}: {line.strip()[:120]}")
