import os
import dotenv
import requests

env = dotenv.dotenv_values('/root/oisha-os/.env')
for k in ['GEMINI_API_KEY', 'GROQ_API_KEY', 'OPENROUTER_API_KEY', 'CEREBRAS_API_KEY', 'MISTRAL_API_KEY', 'SAMBANOVA_API_KEY']:
    val = env.get(k)
    if not val:
        print(f"{k}: not set")
        continue
    # Test Groq
    if k == 'GROQ_API_KEY':
        r = requests.get('https://api.groq.com/openai/v1/models', headers={'Authorization': f'Bearer {val}'}, timeout=5)
        print(f"{k}: status={r.status_code}")
    elif k == 'GEMINI_API_KEY':
        r = requests.get(f'https://generativelanguage.googleapis.com/v1beta/models?key={val}', timeout=5)
        print(f"{k}: status={r.status_code}")
    elif k == 'OPENROUTER_API_KEY':
        r = requests.get('https://openrouter.ai/api/v1/auth/key', headers={'Authorization': f'Bearer {val}'}, timeout=5)
        print(f"{k}: status={r.status_code}")
