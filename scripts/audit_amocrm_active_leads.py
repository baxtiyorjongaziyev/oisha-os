import json
import sys
from collections import defaultdict
import requests

sys.stdout.reconfigure(encoding='utf-8')

def main():
    with open('data/amocrm_token.json') as f:
        tok = json.load(f)['access_token']
    headers = {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}
    base = 'https://jonbranding.amocrm.ru'

    # 1. Fetch all pipelines and status names
    r = requests.get(f'{base}/api/v4/leads/pipelines', headers=headers)
    if r.status_code != 200:
        print("Failed to fetch pipelines:", r.status_code, r.text)
        return
    pipelines = r.json().get('_embedded', {}).get('pipelines', [])
    pipeline_names = {}
    status_names = {}
    for p in pipelines:
        pid = p['id']
        pname = p['name']
        pipeline_names[pid] = pname
        statuses = p.get('_embedded', {}).get('statuses', [])
        for s in statuses:
            status_names[(pid, s['id'])] = s['name']
            status_names[s['id']] = s['name']

    print("=== AMO CRM PIPELINES ===")
    for pid, pname in pipeline_names.items():
        print(f"Pipeline #{pid}: {pname}")

    # 2. Fetch all ACTIVE leads (status_id != 142 and status_id != 143)
    # Note: amoCRM API allows filtering by status or fetching active leads.
    # In amoCRM API v4, we can fetch all leads or filter by status.
    # Let's paginate through leads to get all active leads.
    print("\n=== FETCHING ALL ACTIVE LEADS ===")
    page = 1
    active_leads = []
    closed_count = 0
    
    # We can request leads with contacts
    while True:
        url = f'{base}/api/v4/leads?limit=250&page={page}&with=contacts'
        r = requests.get(url, headers=headers)
        if r.status_code == 204:
            break
        if r.status_code != 200:
            print(f"Error page {page}: {r.status_code}")
            break
        data = r.json()
        leads = data.get('_embedded', {}).get('leads', [])
        if not leads:
            break
        for ld in leads:
            sid = ld.get('status_id')
            # 142 = Won, 143 = Lost
            if sid in (142, 143):
                closed_count += 1
                continue
            active_leads.append(ld)
        page += 1
        print(f"Page {page-1} processed, total active so far: {len(active_leads)}, closed: {closed_count}")

    print(f"\nTOTAL ACTIVE LEADS FOUND: {len(active_leads)}")
    print(f"TOTAL CLOSED LEADS SEEN: {closed_count}")

    # 3. Breakdown of active leads by Pipeline & Status
    pipe_status_counts = defaultdict(int)
    pipe_counts = defaultdict(int)
    for ld in active_leads:
        pid = ld.get('pipeline_id')
        sid = ld.get('status_id')
        pipe_counts[pid] += 1
        pipe_status_counts[(pid, sid)] += 1

    print("\n=== ACTIVE LEADS BREAKDOWN BY PIPELINE ===")
    for pid, count in sorted(pipe_counts.items(), key=lambda x: -x[1]):
        pname = pipeline_names.get(pid, f"Unknown ({pid})")
        print(f"Pipeline #{pid} '{pname}': {count} active leads")
        # List statuses in this pipeline
        for (p_id, s_id), scount in sorted(pipe_status_counts.items(), key=lambda x: -x[1]):
            if p_id == pid:
                sname = status_names.get((p_id, s_id), f"Status {s_id}")
                print(f"    - Status #{s_id} '{sname}': {scount}")

    # 4. Check duplicate leads by name, by contact_id, and by creation time
    print("\n=== ANALYZING DUPLICATES ===")
    leads_by_name = defaultdict(list)
    leads_by_contact = defaultdict(list)
    for ld in active_leads:
        name = ld.get('name', '').strip()
        lid = ld.get('id')
        pid = ld.get('pipeline_id')
        sid = ld.get('status_id')
        created = ld.get('created_at')
        contacts = [c['id'] for c in ld.get('_embedded', {}).get('contacts', [])]
        leads_by_name[name.lower()].append(ld)
        for cid in contacts:
            leads_by_contact[cid].append(ld)

    # Duplicates by Contact ID (same contact has multiple active deals!)
    multideals_by_contact = {cid: lds for cid, lds in leads_by_contact.items() if len(lds) > 1}
    print(f"\nContacts with MULTIPLE ACTIVE DEALS: {len(multideals_by_contact)}")
    dup_deal_count = sum(len(lds) - 1 for lds in multideals_by_contact.values())
    print(f"Potential excess active duplicate deals from multi-deal contacts: {dup_deal_count}")

    for cid, lds in sorted(multideals_by_contact.items(), key=lambda x: -len(x[1]))[:20]:
        print(f"\nContact #{cid} has {len(lds)} active deals:")
        for ld in lds:
            pid = ld.get('pipeline_id')
            sid = ld.get('status_id')
            pname = pipeline_names.get(pid, pid)
            sname = status_names.get(sid, sid)
            print(f"  - Deal #{ld['id']}: '{ld['name']}' | Pipe: {pname} | Status: {sname} | Created: {ld.get('created_at')} | Price: {ld.get('price')}")

    # Duplicates by exact lead Name
    multideals_by_name = {name: lds for name, lds in leads_by_name.items() if len(lds) > 1 and name not in ('', 'yangi bitim', 'bez nazvaniya')}
    print(f"\nLead Names with MULTIPLE ACTIVE DEALS: {len(multideals_by_name)}")
    for name, lds in sorted(multideals_by_name.items(), key=lambda x: -len(x[1]))[:15]:
        print(f"\nName '{name}' has {len(lds)} active deals:")
        for ld in lds:
            pid = ld.get('pipeline_id')
            sid = ld.get('status_id')
            pname = pipeline_names.get(pid, pid)
            sname = status_names.get(sid, sid)
            print(f"  - Deal #{ld['id']} | Pipe: {pname} | Status: {sname} | Created: {ld.get('created_at')}")

if __name__ == '__main__':
    main()
