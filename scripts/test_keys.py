import os
import requests

def test_gemini(key):
    k = key.strip().strip('"').strip("'")
    url = f'https://generativelanguage.googleapis.com/v1beta/models?key={k}'
    try:
        r = requests.get(url, timeout=5)
        return r.status_code == 200, r.status_code, r.text[:100]
    except Exception as e:
        return False, 0, str(e)

def test_groq(key):
    k = key.strip().strip('"').strip("'")
    url = 'https://api.groq.com/openai/v1/models'
    try:
        r = requests.get(url, headers={'Authorization': f'Bearer {k}'}, timeout=5)
        return r.status_code == 200, r.status_code, r.text[:100]
    except Exception as e:
        return False, 0, str(e)

sources = [
    ('.env', '.env'),
    ('contabo', r'C:\Users\baxti\.gemini\antigravity\brain\7e66c384-d055-42a1-847e-bba65dee1847\scratch\contabo_production.env'),
    ('remote', r'C:\Users\baxti\.gemini\antigravity\brain\2f55568d-cee3-42ee-ae62-c7ea71e48e52\scratch\remote.env')
]

for label, path in sources:
    if os.path.exists(path):
        print(f'Checking {label}...')
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if line.startswith('GEMINI_API_KEY='):
                    val = line.split('=', 1)[1].strip()
                    ok, code, txt = test_gemini(val)
                    print(f'  GEMINI_API_KEY: ok={ok}, code={code}')
                if line.startswith('GROQ_API_KEY='):
                    val = line.split('=', 1)[1].strip()
                    ok, code, txt = test_groq(val)
                    print(f'  GROQ_API_KEY: ok={ok}, code={code}')
