import os
import re

vault = r"C:\Users\baxti\Documents\JonBranding Second Brain"
targets = ['rayxona', 'rayhona', 'mumtoz', 'farangiz', 'oydin']
found = []

for root, _, files in os.walk(vault):
    for f in files:
        if f.endswith('.md'):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                for idx, line in enumerate(fp):
                    low = line.lower()
                    if any(t in low for t in targets):
                        phones = re.findall(r'(?:\+?998[\s-]?)?[0-9]{2}[\s-]?[0-9]{3}[\s-]?[0-9]{2}[\s-]?[0-9]{2}', line)
                        tgs = re.findall(r'@[A-Za-z0-9_]+', line)
                        if phones or tgs:
                            found.append((f, idx+1, line.strip()))

for item in found[:30]:
    print(item[0], item[1])
    print("  ", item[2][:140])
