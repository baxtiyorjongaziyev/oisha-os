import json
import os
import sys
import sqlite3
import requests

sys.stdout.reconfigure(encoding='utf-8')

def run_analysis():
    with open('data/amocrm_token.json') as f:
        tok = json.load(f)['access_token']

    headers = {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}
    base = 'https://jonbranding.amocrm.ru'

    print("=== 1. PIPELINES AND STATUSES ===")
    r_pipe = requests.get(f'{base}/api/v4/leads/pipelines', headers=headers)
    pipelines_map = {}
    statuses_map = {}
    if r_pipe.status_code == 200:
        for p in r_pipe.json().get('_embedded', {}).get('pipelines', []):
            pid = p.get('id')
            pname = p.get('name')
            pipelines_map[pid] = pname
            print(f"Pipeline: {pname} (ID: {pid})")
            for s in p.get('_embedded', {}).get('statuses', []):
                sid = s.get('id')
                sname = s.get('name')
                statuses_map[sid] = sname
                print(f"   Status: {sname} (ID: {sid})")

    print("\n=== 2. UNPACKING UNSORTED (NERAZOBRANNOE) ===")
    r = requests.get(f'{base}/api/v4/leads/unsorted', headers=headers)
    unsorted_items = []
    if r.status_code == 200:
        unsorted_items = r.json().get('_embedded', {}).get('unsorted', [])
        print(f"Total unsorted items: {len(unsorted_items)}")
        for u in unsorted_items:
            uid = u.get('uid')
            created_at = u.get('created_at')
            lead = (u.get('_embedded', {}).get('leads') or [{}])[0]
            contact = (u.get('_embedded', {}).get('contacts') or [{}])[0]
            lead_id = lead.get('id')
            lead_name = lead.get('name')
            contact_id = contact.get('id')
            contact_name = contact.get('name')
            
            # Fetch contact details (phone, etc.)
            phone = "N/A"
            contact_custom = []
            if contact_id:
                rc = requests.get(f'{base}/api/v4/contacts/{contact_id}', headers=headers)
                if rc.status_code == 200:
                    cdata = rc.json()
                    c_fields = cdata.get('custom_fields_values') or []
                    for f in c_fields:
                        fname = f.get('field_name')
                        fvals = [v.get('value') for v in f.get('values', [])]
                        contact_custom.append(f"{fname}: {fvals}")
                        if f.get('field_code') == 'PHONE':
                            phone = f['values'][0]['value']
            
            # Fetch lead notes (messages, chats)
            notes_text = []
            if lead_id:
                rn = requests.get(f'{base}/api/v4/leads/{lead_id}/notes', headers=headers)
                if rn.status_code == 200:
                    notes = rn.json().get('_embedded', {}).get('notes', [])
                    for n in notes:
                        params = n.get('params', {})
                        text = params.get('text') or params.get('message') or n.get('note_type')
                        if text:
                            notes_text.append(str(text))
            
            print(f"- LeadID: {lead_id} | Contact: {contact_name} (ID: {contact_id}, Phone: {phone}) | UID: {uid}")
            print(f"  Lead Name: {lead_name}")
            if contact_custom:
                print(f"  Contact fields: {contact_custom}")
            if notes_text:
                print(f"  Notes/Chat: {' | '.join(notes_text[:5])}")
            else:
                print("  Notes/Chat: [No notes found]")

    print("\n=== 3. CHECKING INSTAGRAM DATABASE (data/instagram_comments.db) ===")
    if os.path.exists('data/instagram_comments.db'):
        conn = sqlite3.connect('data/instagram_comments.db')
        c = conn.cursor()
        for tbl in ['user_dm_contacts', 'processed_comments', 'direct_messages']:
            try:
                c.execute(f"SELECT COUNT(*) FROM {tbl}")
                cnt = c.fetchone()[0]
                print(f"Table {tbl}: {cnt} rows")
                c.execute(f"SELECT * FROM {tbl} LIMIT 10")
                rows = c.fetchall()
                for r_item in rows:
                    print(f"   {r_item}")
            except Exception as e:
                print(f"Table {tbl} error: {e}")
        conn.close()

    print("\n=== 4. CHECKING DEALS IN AMOCRM (POTENTIAL MONEY & ACTIVE/CLOSED PIPELINES) ===")
    # Let's inspect leads with price > 0, or in specific statuses (143: Closed Lost, 142: Closed Won, and active statuses)
    r_leads = requests.get(f'{base}/api/v4/leads?limit=250&order[updated_at]=desc&with=contacts', headers=headers)
    if r_leads.status_code == 200:
        all_leads = r_leads.json().get('_embedded', {}).get('leads', [])
        print(f"Fetched {len(all_leads)} leads from AmoCRM")
        
        # Analyze status breakdown & prices
        total_pipeline_val = 0
        total_lost_val = 0
        total_won_val = 0
        lost_leads = []
        active_leads = []
        
        for ld in all_leads:
            lid = ld.get('id')
            lname = ld.get('name')
            price = ld.get('price') or 0
            sid = ld.get('status_id')
            pid = ld.get('pipeline_id')
            status_name = statuses_map.get(sid, f"Status_{sid}")
            pipeline_name = pipelines_map.get(pid, f"Pipeline_{pid}")
            
            if sid == 143: # Closed Lost
                total_lost_val += price
                if price > 0:
                    lost_leads.append((lid, lname, price, status_name, pipeline_name))
            elif sid == 142: # Won
                total_won_val += price
            else:
                total_pipeline_val += price
                if price > 0 or any(kw in lname.lower() for kw in ['brend', 'patent', 'shartnoma', 'to\'lov', 'hisob']):
                    active_leads.append((lid, lname, price, status_name, pipeline_name))

        print(f"Total Won Budget: {total_won_val:,} UZS")
        print(f"Total Lost Budget (deals marked with price): {total_lost_val:,} UZS")
        print(f"Total Active Pipeline Budget: {total_pipeline_val:,} UZS")
        
        print("\nHigh Value or Notable Active Leads:")
        for lid, lname, price, sname, pname in active_leads[:15]:
            print(f"  Deal #{lid}: '{lname}' | Budget: {price:,} UZS | Status: {sname} ({pname})")
            
        print("\nLost Leads with Budgets (Money Left on Table):")
        for lid, lname, price, sname, pname in lost_leads[:15]:
            print(f"  Deal #{lid}: '{lname}' | Budget: {price:,} UZS | Status: {sname} ({pname})")

    print("\n=== 5. CHECKING DUPLICATES IN AMOCRM ===")
    # Fetch contacts
    r_contacts = requests.get(f'{base}/api/v4/contacts?limit=250', headers=headers)
    if r_contacts.status_code == 200:
        contacts = r_contacts.json().get('_embedded', {}).get('contacts', [])
        print(f"Fetched {len(contacts)} contacts for duplicate check")
        phone_map = {}
        name_map = {}
        for c in contacts:
            cid = c.get('id')
            cname = (c.get('name') or '').strip().lower()
            phones = []
            for f in c.get('custom_fields_values') or []:
                if f.get('field_code') == 'PHONE':
                    for val in f.get('values', []):
                        raw_p = val.get('value', '').replace(' ', '').replace('-', '').replace('+', '')
                        if raw_p:
                            phones.append(raw_p)
            for p in phones:
                phone_map.setdefault(p, []).append((cid, c.get('name')))
            if cname:
                name_map.setdefault(cname, []).append((cid, phones))
                
        dup_phones = {p: lst for p, lst in phone_map.items() if len(lst) > 1}
        dup_names = {n: lst for n, lst in name_map.items() if len(lst) > 1}
        print(f"Duplicate phone numbers found: {len(dup_phones)}")
        for p, lst in list(dup_phones.items())[:10]:
            print(f"  Phone {p}: {lst}")
        print(f"Duplicate contact names found: {len(dup_names)}")
        for n, lst in list(dup_names.items())[:10]:
            print(f"  Name '{n}': {lst}")

if __name__ == '__main__':
    run_analysis()
