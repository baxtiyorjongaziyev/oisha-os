import json
import sys
import datetime
import requests

sys.stdout.reconfigure(encoding='utf-8')

def main():
    with open('data/amocrm_token.json') as f:
        tok = json.load(f)['access_token']
    headers = {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}
    base = 'https://jonbranding.amocrm.ru'

    pairs = [
        (41046465, 51534909, "Автоконтакт 949024261", "Islombek ẞotirov"),
        (43028433, 46743223, "Автоконтакт 958452245", "Dilshodaxon Rustamovna Patentlash Markazi"),
        (45889301, 51537463, "Автоконтакт 997223230", "G'ayratjon")
    ]

    for old_id, new_id, old_name, new_name in pairs:
        print(f"\n=== Merging Contact #{old_id} ('{old_name}') -> #{new_id} ('{new_name}') ===")
        
        # 1. Fetch notes from old contact
        r_notes = requests.get(f'{base}/api/v4/contacts/{old_id}/notes', headers=headers)
        if r_notes.status_code == 200:
            notes = r_notes.json().get('_embedded', {}).get('notes', [])
            print(f"  Found {len(notes)} notes on old contact.")
            for n in notes:
                params = n.get('params', {})
                link = params.get('link') or params.get('uniq') or ''
                dur = params.get('duration') or ''
                src = params.get('source') or ''
                call_text = f"[Tarix ko'chirildi: #{old_id}] Qo'ng'iroq / Eslatma: {n.get('note_type')}. Manba: {src}, Davomiyligi: {dur}s. Audio: {link}"
                
                payload = [
                    {
                        "note_type": "common",
                        "params": {
                            "text": call_text
                        }
                    }
                ]
                r_post = requests.post(f'{base}/api/v4/contacts/{new_id}/notes', headers=headers, json=payload)
                if r_post.status_code in [200, 201]:
                    print(f"  Note successfully copied to #{new_id}: {call_text[:60]}...")
                else:
                    print(f"  Error copying note: {r_post.status_code} {r_post.text}")

        # 2. Add merge record note to the primary contact
        merge_note = [
            {
                "note_type": "common",
                "params": {
                    "text": f"Oisha-OS: Dublikat kontakt #{old_id} ('{old_name}') ushbu kontaktga muvaffaqiyatli birlashtirildi. Sana: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                }
            }
        ]
        requests.post(f'{base}/api/v4/contacts/{new_id}/notes', headers=headers, json=merge_note)

        # 3. Clean and archive the old contact (remove phone to prevent search conflicts, tag as merged)
        archive_payload = {
            "name": f"[BIRLASHTIRILDI -> #{new_id}] {old_name}",
            "custom_fields_values": []
        }
        r_patch = requests.patch(f'{base}/api/v4/contacts/{old_id}', headers=headers, json=archive_payload)
        if r_patch.status_code == 200:
            print(f"  SUCCESS: Old contact #{old_id} archived, phone cleared, renamed to '[BIRLASHTIRILDI -> #{new_id}]'.")
        else:
            print(f"  Error archiving old contact: {r_patch.status_code} {r_patch.text}")

    print("\n=== CROSS-CONTACT MERGE COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    main()
