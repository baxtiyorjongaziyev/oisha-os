import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load files
matched_utc = json.load(open('data/matched_high_intent_utc_pipeline.json', 'r', encoding='utf-8'))
hot_verified = json.load(open('data/amocrm_hot_leads_verified.json', 'r', encoding='utf-8'))
utc_cache = json.load(open('data/utc_cache/leads_with_recordings.json', 'r', encoding='utf-8'))

# Index utc_cache by cardNo
utc_by_card = {x['lead'].get('cardNo'): x for x in utc_cache if x.get('lead', {}).get('cardNo')}

# Combine all unique amo lead IDs that need to be moved
# We want leads that are currently in pipeline 11322658 (UTC) or need to be in Sotuv Bo'limi (11162698)
all_to_process = {}

for m in matched_utc:
    lid = m['amo_id']
    if lid not in all_to_process:
        all_to_process[lid] = {
            'lead_id': lid,
            'card_no': m['card_no'],
            'client_name': m['utc_name'],
            'phone': m['phone'],
            'utc_status': m['utc_status'],
            'amo_status': m['amo_status'],
            'source': 'matched_utc',
            'max_dur': m['max_dur'],
            'notes': m['notes']
        }

for h in hot_verified:
    lid = h['lead_id']
    if h['pipeline_id'] == 11322658: # in UTC pipeline
        if lid not in all_to_process:
            all_to_process[lid] = {
                'lead_id': lid,
                'card_no': h['card_no'],
                'client_name': h['client_name'],
                'phone': h['phone'],
                'utc_status': 'HotVerified',
                'amo_status': h['status_id'],
                'source': 'hot_verified',
                'max_dur': 0,
                'notes': ''
            }

# Enrich with UTC card details (comments, form data, etc.)
for lid, item in all_to_process.items():
    c_no = item.get('card_no')
    if c_no in utc_by_card:
        utc_obj = utc_by_card[c_no]
        l = utc_obj['lead']
        item['utc_status'] = l.get('status') or item['utc_status']
        item['notes'] = l.get('notes') or item['notes']
        item['comments'] = [c.get('text', '') for c in utc_obj.get('comments', [])]
        item['form_data'] = l.get('formData')
        item['assigned_operator'] = l.get('assignedToOperatorLogin')
        durs = [r.get('duration', 0) for r in utc_obj.get('recordings', [])]
        item['max_dur'] = max(durs) if durs else item['max_dur']

print(f"Total Unique Leads in amoCRM UTC Pipeline to Move into Sotuv Bo'limi: {len(all_to_process)}")

# Determine appropriate stage in Sotuv Bo'limi (11162698):
# - 88871066: Kelishuv / Yopish (Closing) for 'Sell'
# - 87609526: Uchrashuv (Meeting) for very hot / long call
# - 87609522: Kvalifikatsiya (Qualification) for 'V_PROTSESSE'
# - 87609518: Qayta aloqa (Follow-up) for 'Perezvon' or others

for lid, item in all_to_process.items():
    st = item.get('utc_status', '')
    dur = item.get('max_dur', 0)
    
    if st == 'Sell':
        target_stage = 88871066 # Kelishuv / Yopish
        stage_name = "Kelishuv / Yopish"
        action_task = f"🔥 SHOSHILINCH YOPISH: Mijoz sotuvga tayyor ('Sell' statusi). Zudlik bilan bog'lanib, shartnoma yoki to'lovni rasmiylashtiring!"
    elif st == 'V_PROTSESSE':
        if dur >= 300: # over 5 mins
            target_stage = 87609526 # Uchrashuv
            stage_name = "Uchrashuv"
            action_task = f"📅 UCHRASHUV / KP: Mijoz bilan batafsil suhbat o'tkazilgan ({dur//60} daqiqa). Ehtiyoji bo'yicha taklif berib, online/offline uchrashuvga chaqirish."
        else:
            target_stage = 87609522 # Kvalifikatsiya
            stage_name = "Kvalifikatsiya"
            action_task = f"🎯 KVALIFIKATSIYA: Mijoz 'Jarayonda' (V_PROTSESSE). Ehtiyojini (Logo, Brending, Qadoq) aniqlab, portfolio va narxlar bo'yicha taklif tayyorlash."
    elif st == 'Perezvon':
        target_stage = 87609518 # Qayta aloqa
        stage_name = "Qayta aloqa"
        action_task = f"📞 QAYTA ALOQA: Mijoz qayta qo'ng'iroq qilishni so'ragan. Qulay vaqtda telefon qilib, loyiha talablarini aniqlashtirish."
    else:
        target_stage = 87609518 # Qayta aloqa
        stage_name = "Qayta aloqa"
        action_task = f"📞 QAYTA ALOQA: Targetdan tushgan issiq lid. Qayta bog'lanib, yangi taklif taqdim qilish."
        
    item['target_stage'] = target_stage
    item['target_stage_name'] = stage_name
    item['action_task'] = action_task

leads_list = list(all_to_process.values())
leads_list.sort(key=lambda x: (x['utc_status'] == 'Sell', x['utc_status'] == 'V_PROTSESSE', x['max_dur']), reverse=True)

for i, item in enumerate(leads_list, 1):
    dur_str = f"{item['max_dur']//60}m {item['max_dur']%60}s"
    print(f"{i:2d}. amoID {item['lead_id']} | Card #{item['card_no']:3d} | {item['client_name']:20s} | {item['phone']} | UTC: {item['utc_status']:12s} ({dur_str}) -> Sotuv: {item['target_stage_name']}")

with open('data/target_leads_to_sotuv_final_plan.json', 'w', encoding='utf-8') as f:
    json.dump(leads_list, f, ensure_ascii=False, indent=2)
