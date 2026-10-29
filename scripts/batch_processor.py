import json
import requests
import os
import sys
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8')

# 1. Load credentials
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

# 2. Setup directories
os.makedirs('data/utc_recordings', exist_ok=True)
os.makedirs('data/utc_analysis/transcripts', exist_ok=True)
os.makedirs('data/utc_analysis/deals', exist_ok=True)
os.makedirs('data/utc_analysis/markdown', exist_ok=True)

def safe_filename(s):
    return re.sub(r'[^\w\-_\.]', '_', str(s))

def download_recording(rec_id):
    path = f'data/utc_recordings/{rec_id}.mp3'
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    url = f'https://sales.kontaktmarkazi.com/api/recordings/{rec_id}/file'
    try:
        r = requests.get(url, headers=headers, timeout=60)
        if r.status_code == 200 and len(r.content) > 1000:
            with open(path, 'wb') as f:
                f.write(r.content)
            return path
    except Exception as e:
        print(f'Error downloading {rec_id}: {e}')
    return None

def transcribe_audio(audio_path):
    cache_path = f'data/utc_analysis/transcripts/{os.path.basename(audio_path)}.json'
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    
    try:
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
            print(f'Transcription API error {r.status_code}: {r.text[:150]}')
    except Exception as e:
        print(f'Transcription exception {audio_path}: {e}')
    return None

def analyze_transcript(lead_info, transcript_text, comments):
    card_no = lead_info.get('cardNo')
    name = lead_info.get('name')
    phone = lead_info.get('phoneNumber')
    status = lead_info.get('status')
    op_name = (lead_info.get('assignedToOperator') or {}).get('fullName', 'Noma\'lum')
    op_login = lead_info.get('assignedToOperatorLogin', '')

    comments_str = '\n'.join([f"- {c.get('date', '')} ({c.get('by', '')}): {c.get('text', '')}" for c in comments]) if comments else "Izohlar yo'q"

    prompt = f"""Siz Jon Branding kompaniyasining B2B Savdo Bo'yicha Bosh Direktori va Sifat Auditorisiz.
Quyida Uztelecom outsource call-markaz (UTC Contact Pulse) sotuv operatori va mijoz o'rtasidagi qo'ng'iroq(lar) transkripti berilgan.
Mijoz ma'lumotlari va qo'ng'iroqlarni to'liq tahlil qilib, Jon Branding ichki AmoCRM sotuv jamoasi (Closerlar) uchun professional, aniq va amaliy operatsion tahlil hujjati tayyorlang.

MIJOZ MA'LUMOTLARI:
- CRM Karta raqami: #{card_no}
- Ismi: {name}
- Telefon: {phone}
- Outsource statusi: {status}
- Outsource operatori: {op_name} (#{op_login})
- Mavjud izohlar:
{comments_str}

QO'NG'IROQLAR TRANSKRIPTI:
\"\"\"
{transcript_text[:12000]}
\"\"\"

Qat'iy ravishda quyidagi JSON formatida javob bering:
{{
  "card_no": {card_no if card_no else 0},
  "client_name": "{name}",
  "phone": "{phone}",
  "utc_status": "{status}",
  "real_status": "<Aniq status: Tayyor_Sotuv / Qayta_Aloqa / Potensial_Issiq / Qiziqmadi / Xato_Raqam / Bog'lanib_Bo'lmadi>",
  "need_and_context": "<Mijozning asosiy ehtiyoji, biznes sohasi, brend nomi, qanday xizmat kerakligi>",
  "bant_analysis": {{
    "budget": "<Byudjeti, narxga munosabati, to'lov qobiliyati>",
    "authority": "<Qaror qabul qiluvchi o'zimi yoki boshqa sherik/rahbar bormi>",
    "need": "<Ehtiyoj darajasi: Yuqori / O'rta / Past>",
    "timeline": "<Qachon boshlamoqchi, muddat>"
  }},
  "operator_errors": [
    "<Operatorning 1-kamchiligi/xatosi>",
    "<Operatorning 2-kamchiligi/xatosi>"
  ],
  "client_objections": [
    "<Mijozning asosiy e'tirozi, ikkilanishi yoki to'xtab qolish sababi>"
  ],
  "amocrm_strategy": {{
    "target_pipeline": "<Tavsiya etilgan voronka: Sotuv Bo'limi / Closer>",
    "target_stage": "<Tavsiya etilgan bosqich: Maslahat tayinlandi / Qayta aloqa / O'ylab ko'rmoqda / Yopildi>",
    "priority": "<Yuqori (P1) / O'rta (P2) / Past (P3)>",
    "call_opening_hook": "<AmoCRM menejeri qo'ng'iroq qilganda aytishi kerak bo'lgan birinchi aniq jumla (kirish skripti)>",
    "closing_pitch": "<Mijozni bitimga olib boruvchi yechim va yopish taklifi>"
  }},
  "summary_uz": "<Closer menejerlar uchun 3-4 gapdan iborat qisqa, aniq va foydali operatsion xulosa>"
}}
"""
    url = 'https://api.groq.com/openai/v1/chat/completions'
    models = ['openai/gpt-oss-20b', 'qwen/qwen3.8-27b', 'openai/gpt-oss-120b']
    
    for model_name in models:
        for attempt in range(3):
            payload = {
                'model': model_name,
                'messages': [
                    {'role': 'system', 'content': 'You are a Senior B2B Sales Director at Jon Branding. Return strictly valid JSON.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.1,
                'response_format': {'type': 'json_object'}
            }
            try:
                r = requests.post(url, headers={'Authorization': f'Bearer {gkey}'}, json=payload, timeout=60)
                if r.status_code == 200:
                    content = r.json()['choices'][0]['message']['content']
                    return json.loads(content)
                elif r.status_code == 429:
                    print(f'   [429 rate limit on {model_name}, waiting 4s (attempt {attempt+1})...]')
                    time.sleep(4)
                else:
                    print(f'   [LLM error {r.status_code} on {model_name}: {r.text[:100]}]')
                    break
            except Exception as e:
                print(f'   [LLM exception on {model_name}: {e}]')
                time.sleep(2)
    return None

def generate_markdown(lead, recs, analysis, combined_text):
    ld = lead
    card_no = ld.get('cardNo')
    name = ld.get('name')
    phone = ld.get('phoneNumber')
    utc_status = ld.get('status')
    real_status = analysis.get('real_status', utc_status)
    bant = analysis.get('bant_analysis', {})
    strat = analysis.get('amocrm_strategy', {})
    
    op_name = (ld.get('assignedToOperator') or {}).get('fullName', 'Noma\'lum')
    tot_dur = sum(r.get('duration_sec', 0) for r in recs)
    
    errors_md = '\n'.join([f"- ⚠️ {e}" for e in analysis.get('operator_errors', [])])
    obj_md = '\n'.join([f"- ❓ {o}" for o in analysis.get('client_objections', [])])
    
    target_pipeline = strat.get('target_pipeline', "Sotuv Bo'limi")
    target_stage = strat.get('target_stage', 'Maslahat tayinlandi')
    need_context = analysis.get('need_and_context', "Ma'lumot yo'q")
    closing_pitch = strat.get('closing_pitch', 'Mijozga individual yechim taklif qilinadi.')

    md = f"""# Sdelka Tahlili: #{card_no} — {name}

## 📋 Pasport Ma'lumotlari
| Ko'rsatkich | Qiymat |
| :--- | :--- |
| **Karta raqami** | `#{card_no}` |
| **Mijoz ismi** | **{name}** |
| **Telefon raqami** | `+{phone}` |
| **UTC CRM Statusi** | `{utc_status}` |
| **Haqiqiy Real Statusi** | **{real_status}** |
| **Jami qo'ng'iroqlar** | {len(recs)} ta ({tot_dur} sek / {tot_dur/60:.1f} daqiqa) |
| **UTC Mas'ul Operator** | {op_name} |
| **Prioritet (AmoCRM)** | **{strat.get('priority', 'Yuqori')}** |

---

## 🎯 1. Mijozning Ehtiyoji va Biznes Konteksti
{need_context}

---

## 📊 2. BANT Tahlili
- 💰 **Budget (Byudjet):** {bant.get('budget', 'Aniqlanmagan')}
- 👤 **Authority (Qaror qabul qiluvchi):** {bant.get('authority', 'Aniqlanmagan')}
- ⚡ **Need (Ehtiyoj darajasi):** {bant.get('need', 'Aniqlanmagan')}
- ⏱️ **Timeline (Muddat):** {bant.get('timeline', 'Aniqlanmagan')}

---

## ⚠️ 3. Outsource (UTC) Operatorining Xatolari
{errors_md if errors_md else "- Operator tomonidan qo'pol xatoliklar kuzatilmadi."}

---

## ❓ 4. Mijozning E'tirozlari va Ikkilanishlari
{obj_md if obj_md else "- Aniq e'tiroz bildirilmagan."}

---

## 🚀 5. AmoCRM Menejerlari (Closerlar) Uchun Aniq Taktik Yo'riqnoma
- **Tavsiya etilgan voronka:** `{target_pipeline}`
- **Tavsiya etilgan bosqich:** `{target_stage}`
- **📞 Kirish so'zlari (Opening Hook):**
> *"{strat.get('call_opening_hook', 'Assalomu alaykum!')}"*
- **💼 Yopish strategiyasi (Closing Pitch):**
> *{closing_pitch}*

---

## 📝 6. Qisqa Xulosa
{analysis.get('summary_uz', '')}

---

<details>
<summary><b>📜 To'liq Qo'ng'iroqlar Transkripti (Ko'rish uchun bosing)</b></summary>

```text
{combined_text}
```
</details>
"""
    return md

def process_single_lead_full(lead_item):
    ld = lead_item['lead']
    recs = lead_item['recordings']
    comments = lead_item.get('comments', [])
    card_no = ld.get('cardNo')
    name = ld.get('name', 'Client')
    safe_name = safe_filename(f"{card_no}_{name}")

    json_out_path = f'data/utc_analysis/deals/{safe_name}.json'
    md_out_path = f'data/utc_analysis/markdown/{safe_name}.md'

    # If already fully analyzed, load from cache
    if os.path.exists(json_out_path) and os.path.exists(md_out_path):
        with open(json_out_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    # 1. Download recordings
    full_transcripts = []
    for idx, r in enumerate(recs):
        rec_id = r.get('recording_id')
        dur = r.get('duration_sec', 0)
        if not rec_id or dur <= 0:
            continue
        audio_file = download_recording(rec_id)
        if audio_file:
            tr = transcribe_audio(audio_file)
            if tr and tr.get('text'):
                full_transcripts.append(f"--- QO'NG'IROQ {idx+1} ({dur} sek, {r.get('created_at')}) ---\n" + tr.get('text', ''))

    if not full_transcripts:
        return None

    combined_text = '\n\n'.join(full_transcripts)

    # 2. Analyze
    analysis = analyze_transcript(ld, combined_text, comments)
    if not analysis:
        return None

    analysis['full_transcripts'] = combined_text
    analysis['recordings_count'] = len(recs)
    analysis['total_duration_sec'] = sum(r.get('duration_sec', 0) for r in recs)

    # 3. Save JSON
    with open(json_out_path, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    # 4. Generate & Save Markdown
    md = generate_markdown(ld, recs, analysis, combined_text)
    with open(md_out_path, 'w', encoding='utf-8') as f:
        f.write(md)

    return analysis

def main():
    with open('data/utc_cache/leads_with_recordings.json', 'r', encoding='utf-8') as f:
        leads = json.load(f)

    # Select target leads to process:
    # 1. All Sell (2)
    # 2. All V_PROTSESSE (38)
    # 3. All Perezvon (9)
    # 4. Top 30 longest Not interested (duration >= 300s)
    # 5. Top 10 longest Busy (duration >= 60s)

    sell = [l for l in leads if l['lead'].get('status') == 'Sell']
    v_proc = [l for l in leads if l['lead'].get('status') == 'V_PROTSESSE']
    perez = [l for l in leads if l['lead'].get('status') == 'Perezvon']
    not_int = sorted([l for l in leads if l['lead'].get('status') == 'Not interested'], 
                     key=lambda l: sum(r['duration_sec'] for r in l['recordings']), reverse=True)[:35]
    busy = sorted([l for l in leads if l['lead'].get('status') == 'Busy'], 
                  key=lambda l: sum(r['duration_sec'] for r in l['recordings']), reverse=True)[:15]

    targets = sell + v_proc + perez + not_int + busy
    print(f'Starting processing of {len(targets)} high-value deals...')
    print(f'  Sell: {len(sell)}')
    print(f'  V_PROTSESSE: {len(v_proc)}')
    print(f'  Perezvon: {len(perez)}')
    print(f'  Longest Not interested: {len(not_int)}')
    print(f'  Longest Busy: {len(busy)}')

    results = []
    start_time = time.time()

    # Process sequentially or with small pool to ensure reliable transcription & LLM
    for idx, item in enumerate(targets):
        c_no = item['lead'].get('cardNo')
        c_name = item['lead'].get('name')
        st = item['lead'].get('status')
        dur = sum(r['duration_sec'] for r in item['recordings'])
        print(f'[{idx+1}/{len(targets)}] Processing #{c_no} {c_name} ({st}, {dur}s)...')
        res = process_single_lead_full(item)
        if res:
            results.append(res)
            print(f'   -> Done! Real: {res.get("real_status")}, Priority: {res.get("amocrm_strategy", {}).get("priority")}')
        else:
            print(f'   -> Skipped or failed.')

    elapsed = time.time() - start_time
    print(f'\nFinished processing {len(results)} deals in {elapsed:.1f}s ({elapsed/60:.1f} mins)!')

    # Save master summary
    with open('data/utc_analysis/master_registry.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print('Master registry saved to data/utc_analysis/master_registry.json')

if __name__ == '__main__':
    main()
