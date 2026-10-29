import json
import requests
import os
import sys
import time

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

os.makedirs('data/utc_recordings', exist_ok=True)
os.makedirs('data/utc_analysis/transcripts', exist_ok=True)
os.makedirs('data/utc_analysis/deals', exist_ok=True)

def download_recording(rec_id):
    path = f'data/utc_recordings/{rec_id}.mp3'
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    url = f'https://sales.kontaktmarkazi.com/api/recordings/{rec_id}/file'
    r = requests.get(url, headers=headers, timeout=60)
    if r.status_code == 200 and len(r.content) > 1000:
        with open(path, 'wb') as f:
            f.write(r.content)
        return path
    return None

def transcribe_audio(audio_path):
    cache_path = f'data/utc_analysis/transcripts/{os.path.basename(audio_path)}.json'
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    with open(audio_path, 'rb') as f:
        files = {'file': (os.path.basename(audio_path), f, 'audio/mpeg')}
        data = {
            'model': 'whisper-large-v3-turbo',
            'language': 'uz',
            'response_format': 'verbose_json',
            'temperature': 0.0
        }
        r = requests.post(
            'https://api.groq.com/openai/v1/audio/transcriptions',
            headers={'Authorization': f'Bearer {gkey}'},
            files=files,
            data=data,
            timeout=180
        )
    if r.status_code == 200:
        res = r.json()
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        return res
    else:
        print(f'Transcription error {r.status_code}: {r.text}')
        return None

def analyze_transcript_groq(lead_info, transcript_text):
    prompt = f"""Quyida Jon Branding agentligining Uztelecom (UTC) outsource sotuv operatori va mijoz o'rtasidagi telefon suhbati transkripti keltirilgan.
Ushbu sdelkani to'liq tahlil qilib, Jon Branding ichki AmoCRM sotuv menejerlari (Closerlari) uchun mukammal operatsion hujjat tayyorla.

MIJOZ MA'LUMOTLARI (UTC CRM):
- Karta raqami: #{lead_info.get('cardNo')}
- Ismi: {lead_info.get('name')}
- Telefon: {lead_info.get('phoneNumber')}
- UTC Statusi: {lead_info.get('status')}
- Voronka/Doska: {lead_info.get('board')}
- Mas'ul operator: {lead_info.get('assignedToOperator', {}).get('fullName')} ({lead_info.get('assignedToOperatorLogin')})

SUHBAT TRANSKRIPTI:
\"\"\"
{transcript_text[:12000]}
\"\"\"

Qat'iy ravishda quyidagi JSON formatida javob ber (boshqa ortiqcha matnsiz, faqat toza JSON):
{{
  "card_no": {lead_info.get('cardNo')},
  "client_name": "{lead_info.get('name')}",
  "phone": "{lead_info.get('phoneNumber')}",
  "utc_status": "{lead_info.get('status')}",
  "real_status": "<Aniq baho: Tayyor_Sotuv / Qayta_Aloqa / Potensial_Issiq / Qiziqmadi / Xato_Raqam>",
  "need_and_context": "<Mijozning asosiy maqsadi, biznes sohasi, brend nomi, nima xohlayotgani>",
  "bant_analysis": {{
    "budget": "<Mijozning byudjeti, narxga munosabati, to'lovga tayyorligi>",
    "authority": "<Qaror qabul qiluvchi shaxsmi yoki sherik/rahbar bormi>",
    "need": "<Ehtiyoj darajasi: Yuqori / O'rta / Past>",
    "timeline": "<Qachon boshlamoqchi>"
  }},
  "operator_errors": [
    "<Operatorning 1-xatosi>",
    "<Operatorning 2-xatosi>"
  ],
  "client_objections": [
    "<Mijoz bildirgan e'tiroz yoki ikkilanish>"
  ],
  "amocrm_strategy": {{
    "target_pipeline": "<Sotuv Bo'limi / Closer>",
    "target_stage": "<Maslahat tayinlandi / Qayta aloqa / O'ylab ko'rmoqda>",
    "call_opening_hook": "<AmoCRM menejeri qo'ng'iroqni qanday so'zlar bilan boshlashi kerak (aniq gap)>",
    "closing_pitch": "<Mijozga qanday yechim taklif qilish va qanday yopish kerak>"
  }},
  "summary_uz": "<Menejerlar uchun 3-4 gapdan iborat qisqa, lo'nda va amaliy xulosa>"
}}
"""
    # Call Groq LLM (e.g. openai/gpt-oss-120b or qwen/qwen3.8-27b)
    url = 'https://api.groq.com/openai/v1/chat/completions'
    payload = {
        'model': 'openai/gpt-oss-120b',
        'messages': [
            {'role': 'system', 'content': 'You are a Senior B2B Sales Director and Call Quality Auditor at Jon Branding Agency. Return only valid JSON.'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.1,
        'response_format': {'type': 'json_object'}
    }
    r = requests.post(url, headers={'Authorization': f'Bearer {gkey}'}, json=payload, timeout=60)
    if r.status_code == 200:
        return json.loads(r.json()['choices'][0]['message']['content'])
    else:
        print(f'LLM error {r.status_code}: {r.text}')
        return None

# Test on Lead #135 Mirzohidjon
with open('data/utc_cache/leads_with_recordings.json', 'r', encoding='utf-8') as f:
    leads = json.load(f)

lead_obj = next(l for l in leads if str(l['lead'].get('cardNo')) == '135')
ld = lead_obj['lead']
recs = lead_obj['recordings']
print(f'Processing Lead #{ld.get("cardNo")} {ld.get("name")}...')

full_transcripts = []
for idx, r in enumerate(recs):
    rec_id = r['recording_id']
    print(f'  Downloading rec {idx+1}/{len(recs)}: {rec_id} ({r["duration_sec"]}s)...')
    audio_file = download_recording(rec_id)
    if audio_file:
        print(f'  Transcribing {rec_id}...')
        tr = transcribe_audio(audio_file)
        if tr:
            full_transcripts.append(f'--- QO\'NG\'IROQ {idx+1} ({r["duration_sec"]} sek, {r["created_at"]}) ---\n' + tr.get('text', ''))

combined_text = '\n\n'.join(full_transcripts)
print(f'Total transcript length: {len(combined_text)} chars')

print('Running AI Call Analysis...')
analysis = analyze_transcript_groq(ld, combined_text)
print('Analysis result:')
print(json.dumps(analysis, ensure_ascii=False, indent=2))
