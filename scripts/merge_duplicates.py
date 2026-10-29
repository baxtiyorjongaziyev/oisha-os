import json
import sys
import requests

sys.stdout.reconfigure(encoding='utf-8')

def main():
    with open('data/amocrm_token.json') as f:
        tok = json.load(f)['access_token']
    headers = {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}
    base = 'https://jonbranding.amocrm.ru'

    print("==================================================")
    print("STEP 1: MERGING 3 CROSS-CONTACT DUPLICATE PAIRS")
    print("==================================================")
    pairs = [
        (41046465, 51534909, "Автоконтакт 949024261 -> Islombek ẞotirov"),
        (43028433, 46743223, "Автоконтакт 958452245 -> Dilshodaxon Rustamovna Patentlash Markazi"),
        (45889301, 51537463, "Автоконтакт 997223230 -> G'ayratjon")
    ]

    for old_id, new_id, desc in pairs:
        print(f"\nProcessing: {desc}")
        # 1. Fetch notes from old contact
        r_notes = requests.get(f'{base}/api/v4/contacts/{old_id}/notes', headers=headers)
        if r_notes.status_code == 200:
            notes = r_notes.json().get('_embedded', {}).get('notes', [])
            print(f"  Migrating {len(notes)} notes from Contact #{old_id} to Contact #{new_id}...")
            for n in notes:
                ntype = n.get('note_type', 'common')
                params = n.get('params', {})
                payload = [
                    {
                        "note_type": ntype,
                        "params": params
                    }
                ]
                rn_post = requests.post(f'{base}/api/v4/contacts/{new_id}/notes', headers=headers, json=payload)
                if rn_post.status_code in [200, 201]:
                    print(f"    Note migrated: {ntype}")
                else:
                    print(f"    Note migration error ({rn_post.status_code}): {rn_post.text}")

        # 2. Check if old contact has any leads linked
        r_old = requests.get(f'{base}/api/v4/contacts/{old_id}?with=leads', headers=headers)
        if r_old.status_code == 200:
            old_leads = r_old.json().get('_embedded', {}).get('leads', [])
            for ld in old_leads:
                lid = ld.get('id')
                print(f"  Re-linking lead #{lid} to Contact #{new_id}...")
                # Link lead to new contact
                patch_payload = {
                    "_embedded": {
                        "contacts": [{"id": new_id}]
                    }
                }
                requests.patch(f'{base}/api/v4/leads/{lid}', headers=headers, json=patch_payload)

        # 3. Delete the old duplicate contact
        r_del = requests.delete(f'{base}/api/v4/contacts/{old_id}', headers=headers)
        if r_del.status_code in [200, 204]:
            print(f"  SUCCESS: Old duplicate contact #{old_id} deleted successfully.")
        else:
            print(f"  Delete status: {r_del.status_code} ({r_del.text})")

    print("\n==================================================")
    print("STEP 2: CLEANING INTRA-CONTACT DUPLICATE PHONES")
    print("==================================================")
    target_cids = [
        42816939, 42834915, 42825245, 42907059, 42981445, 42961711,
        51528651, 43225697, 51932589, 43934029, 42811527, 54039080,
        53876266, 53514936, 54830700, 55490296, 55551472, 56068489
    ]

    for cid in target_cids:
        r = requests.get(f'{base}/api/v4/contacts/{cid}', headers=headers)
        if r.status_code != 200:
            print(f"Contact #{cid} fetch error {r.status_code}")
            continue

        cdata = r.json()
        cname = cdata.get('name')
        cf_values = cdata.get('custom_fields_values') or []
        phone_field = None
        other_fields = []

        for fld in cf_values:
            if fld.get('field_code') == 'PHONE':
                phone_field = fld
            else:
                other_fields.append(fld)

        if not phone_field:
            continue

        existing_vals = phone_field.get('values', [])
        seen_numbers = set()
        deduped_vals = []

        for val_obj in existing_vals:
            raw_v = val_obj.get('value', '')
            norm_v = raw_v.replace(' ', '').replace('-', '').replace('+', '').replace('(', '').replace(')', '')
            if norm_v and norm_v not in seen_numbers:
                seen_numbers.add(norm_v)
                deduped_vals.append(val_obj)

        if len(deduped_vals) < len(existing_vals):
            print(f"Contact #{cid} '{cname}': reduced phone entries from {len(existing_vals)} to {len(deduped_vals)}")
            phone_field['values'] = deduped_vals
            new_cf_values = other_fields + [phone_field]
            patch_data = {
                "custom_fields_values": new_cf_values
            }
            rp = requests.patch(f'{base}/api/v4/contacts/{cid}', headers=headers, json=patch_data)
            if rp.status_code == 200:
                print(f"  SUCCESS: Contact #{cid} updated without duplicate phones.")
            else:
                print(f"  Update error ({rp.status_code}): {rp.text}")
        else:
            print(f"Contact #{cid} '{cname}': already has unique phone entries ({len(deduped_vals)})")

    print("\n=== DEDUPLICATION COMPLETE ===")

if __name__ == '__main__':
    main()
