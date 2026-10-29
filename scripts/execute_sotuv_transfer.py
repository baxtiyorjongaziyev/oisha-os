import json
import sys
import io
import time
import re
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {
    'Authorization': f"Bearer {token['access_token']}",
    'Content-Type': 'application/json'
}

plan = json.load(open('data/target_leads_to_sotuv_final_plan.json', 'r', encoding='utf-8'))

# Deduplicate by lead_id
unique_leads = {}
for item in plan:
    lid = item['lead_id']
    if lid not in unique_leads:
        unique_leads[lid] = item

print(f"Loaded {len(unique_leads)} unique leads to transfer into Sotuv Bo'limi.", flush=True)

# Helper to extract form details from comments
def extract_meta_details(comments):
    info = {}
    for c in comments:
        if 'Barcha savol-javoblar:' in c:
            for pair in c.split('Barcha savol-javoblar:')[-1].split('|'):
                if ':' in pair:
                    k, v = pair.split(':', 1)
                    info[k.strip()] = v.strip()
        for line in c.split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                k_clean = k.strip().lower()
                if 'brend nomi' in k_clean:
                    info['brand_name'] = v.strip()
                elif 'faoliyat sohasi' in k_clean:
                    info['industry'] = v.strip()
                elif 'asosiy maqsad' in k_clean:
                    info['goal'] = v.strip()
                elif 'tadbirkorlik holati' in k_clean:
                    info['business_state'] = v.strip()
    return info

# Prepare batch data
processed_results = []
complete_till = int(time.time()) + 4 * 3600 # 4 hours from now

for i, (lid, item) in enumerate(unique_leads.items(), 1):
    c_no = item.get('card_no')
    name = item.get('client_name', 'Mijoz')
    phone = item.get('phone', '')
    utc_st = item.get('utc_status', '')
    dur = item.get('max_dur', 0)
    comments = item.get('comments', [])
    notes = item.get('notes', '')
    
    meta_info = extract_meta_details(comments)
    brand = meta_info.get('brand_name') or meta_info.get('brendingiz_yoki_bisnesingiz_nomi_nima') or ''
    industry = meta_info.get('industry') or meta_info.get('siz_qaysi_sohada_faoliyat_yuritasiz') or ''
    goal = meta_info.get('goal') or meta_info.get('brendni_patentlashdan_asosiy_maqsadingiz_nima') or ''
    b_state = meta_info.get('business_state') or meta_info.get('tadbirkorlik_holatingiz_qanday') or ''
    
    # Target stage
    if utc_st == 'Sell':
        stage_id = 88871066 # Kelishuv / Yopish
        stage_name = "Kelishuv / Yopish"
        prefix = "🔥 SHOSHILINCH YOPISH (Sell statusi)"
    elif utc_st == 'V_PROTSESSE':
        if dur >= 300:
            stage_id = 87609526 # Uchrashuv
            stage_name = "Uchrashuv"
            prefix = "📅 UCHRASHUV / KP"
        else:
            stage_id = 87609522 # Kvalifikatsiya
            stage_name = "Kvalifikatsiya"
            prefix = "🎯 KVALIFIKATSIYA"
    elif utc_st == 'Perezvon':
        stage_id = 87609518 # Qayta aloqa
        stage_name = "Qayta aloqa"
        prefix = "📞 QAYTA ALOQA (Mijoz so'ragan)"
    else:
        stage_id = 87609518 # Qayta aloqa
        stage_name = "Qayta aloqa"
        prefix = "📞 QAYTA ALOQA (Target Lead)"
        
    details_part = []
    if brand:
        details_part.append(f"Brend: '{brand}'")
    if industry:
        details_part.append(f"Soha: {industry}")
    if goal:
        details_part.append(f"Maqsad: {goal}")
    if notes:
        details_part.append(f"Qayd: {notes}")
    details_str = " | ".join(details_part) if details_part else f"Tel: {phone}"
    
    task_text = f"{prefix}: {details_str}. Zudlik bilan bog'lanib, Jon Branding bo'yicha taklif berish va keyingi bosqichga o'tkazish."
    if len(task_text) > 250:
        task_text = task_text[:247] + "..."
        
    print(f"[{i:2d}/{len(unique_leads)}] Moving Lead {lid} ({name}) to '{stage_name}'...", flush=True)
    
    # 1. PATCH Lead to pipeline 11162698
    patch_data = [{
        "id": lid,
        "pipeline_id": 11162698,
        "status_id": stage_id,
        "responsible_user_id": 13021974
    }]
    r_p = requests.patch('https://jonbranding.amocrm.ru/api/v4/leads', headers=headers, json=patch_data, timeout=15)
    patch_ok = (r_p.status_code == 200)
    
    # 2. POST Task
    task_id = None
    if patch_ok:
        task_data = [{
            "entity_id": lid,
            "entity_type": "leads",
            "text": task_text,
            "complete_till": complete_till,
            "task_type_id": 1,
            "responsible_user_id": 13021974
        }]
        r_t = requests.post('https://jonbranding.amocrm.ru/api/v4/tasks', headers=headers, json=task_data, timeout=15)
        if r_t.status_code == 200:
            tasks_resp = r_t.json().get('_embedded', {}).get('tasks', [])
            if tasks_resp:
                task_id = tasks_resp[0].get('id')
                
    # 3. POST Note for sales dossier
    note_ok = False
    if patch_ok and details_part:
        note_text = (
            f"📋 TARGET LEADS KVALIFIKATSIYA DOSYESI\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Mijoz: {name} ({phone})\n"
            f"• UTC Karta: #{c_no} (Status: {utc_st})\n"
            f"• Brend nomi: {brand or 'Noma\'lum'}\n"
            f"• Faoliyat sohasi: {industry or 'Noma\'lum'}\n"
            f"• Holat: {b_state or 'Noma\'lum'}\n"
            f"• Asosiy maqsad: {goal or 'Noma\'lum'}\n"
            f"• Operator qaydi: {notes or 'Yo\'q'}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Vazifa: Sotuv bo'limi menejeri zudlik bilan bog'lanib, konsultatsiya berishi zarur."
        )
        note_data = [{
            "note_type": "common",
            "params": {"text": note_text}
        }]
        r_n = requests.post(f'https://jonbranding.amocrm.ru/api/v4/leads/{lid}/notes', headers=headers, json=note_data, timeout=15)
        note_ok = (r_n.status_code == 200)

    print(f"    Result: PATCH={patch_ok}, TaskID={task_id}, Note={note_ok}", flush=True)
    
    processed_results.append({
        'lead_id': lid,
        'card_no': c_no,
        'name': name,
        'phone': phone,
        'utc_status': utc_st,
        'target_stage_id': stage_id,
        'target_stage_name': stage_name,
        'task_id': task_id,
        'task_text': task_text,
        'brand': brand,
        'industry': industry,
        'goal': goal,
        'patch_success': patch_ok,
        'note_success': note_ok
    })
    
    time.sleep(0.3)

with open('data/amocrm_transferred_sotuv_leads_report.json', 'w', encoding='utf-8') as f_out:
    json.dump(processed_results, f_out, ensure_ascii=False, indent=2)

print("\nAll leads processed and saved to data/amocrm_transferred_sotuv_leads_report.json!", flush=True)
