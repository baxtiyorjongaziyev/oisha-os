import requests
r = requests.get('http://127.0.0.1:8080/api/crm/dialer/kanban?pipeline_id=11162698&tag=Rayxon').json()
print('Total leads for Rayxon:', r.get('total_leads'))
for st in r.get('stages', []):
    if st.get('count', 0) > 0:
        print(f"  {st.get('title')}: {st.get('count')} ta bitim")
