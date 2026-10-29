import json
import requests
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('data/utc_session.json', 'r', encoding='utf-8') as f:
    sess = json.load(f)

with open('.env', 'r', encoding='utf-8') as f:
    env = dict(line.strip().split('=', 1) for line in f if '=' in line and not line.startswith('#'))

gkey = env.get('GROQ_API_KEY', '').strip()

headers = {
    'Authorization': f'Bearer {sess["token"]}',
    'x-company-id': sess.get('company', 'company_default'),
    'Accept': 'application/json',
    'User-Agent': 'Mozilla/5.0'
}

with open('data/utc_cache/leads_with_recordings.json', 'r', encoding='utf-8') as f:
    leads = json.load(f)

# Find a lead in Sell or V_PROTSESSE
target_lead = next(l for l in leads if l['lead'].get('status') == 'Sell')
print('Target lead:', target_lead['lead'].get('name'), target_lead['lead'].get('phoneNumber'), target_lead['lead'].get('status'))
rec = target_lead['recordings'][0]
rec_id = rec['recording_id']
duration = rec['duration_sec']
print(f'Recording ID: {rec_id}, duration: {duration}s')

os.makedirs('data/utc_recordings', exist_ok=True)
audio_path = f'data/utc_recordings/test_{rec_id}.mp3'

# Download audio
print('Downloading audio...')
rec_url = f'https://sales.kontaktmarkazi.com/api/recordings/{rec_id}/file'
r = requests.get(rec_url, headers=headers)
with open(audio_path, 'wb') as f:
    f.write(r.content)
print(f'Downloaded {len(r.content)} bytes to {audio_path}')

# Transcribe with Groq Whisper
print('Transcribing with Groq whisper-large-v3...')
with open(audio_path, 'rb') as f:
    files = {
        'file': (os.path.basename(audio_path), f, 'audio/mpeg')
    }
    data = {
        'model': 'whisper-large-v3',
        'language': 'uz',
        'response_format': 'verbose_json',
        'temperature': 0.0
    }
    groq_headers = {
        'Authorization': f'Bearer {gkey}'
    }
    resp = requests.post(
        'https://api.groq.com/openai/v1/audio/transcriptions',
        headers=groq_headers,
        files=files,
        data=data,
        timeout=120
    )

if resp.status_code == 200:
    res_data = resp.json()
    text = res_data.get('text', '')
    print('\n=== TRANSCRIPTION ===')
    print(text)
    print('\nSegments count:', len(res_data.get('segments', [])))
else:
    print('Groq STT error:', resp.status_code, resp.text)
