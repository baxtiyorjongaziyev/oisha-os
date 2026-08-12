import requests, json, sys, os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath('.'))
from src.settings import settings
from src.services.core.crm.amocrm_sync import AmoCRMSync

def is_junk_name(name):
    lower_name = str(name).lower()
    junk_keywords = ['test', 'тест', 'spam', 'спам', '123', 'qwe', 'asd']
    for kw in junk_keywords:
        if kw in lower_name:
            return True
    return False

def main():
    amocrm = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET,
        redirect_url=settings.AMOCRM_REDIRECT_URL,
    )
    headers = amocrm._get_headers()
    thirty_days_ago = int((datetime.now() - timedelta(days=30)).timestamp())
    
    junk_leads = []
    page = 1
    
    print("Fetching active leads and analyzing...")
    while True:
        url = f'{amocrm.base_url}/api/v4/leads?with=contacts&limit=250&page={page}'
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json().get('_embedded', {}).get('leads', [])
            if not data:
                break
            
            for l in data:
                if l['status_id'] in (142, 143):
                    continue
                
                is_junk = False
                reason = ""
                
                if is_junk_name(l.get('name', '')):
                    is_junk = True
                    reason = "Shubhali ism (Test/Spam)"
                
                contacts = l.get('_embedded', {}).get('contacts', [])
                if not contacts:
                    is_junk = True
                    reason = "Kontakt biriktirilmagan"
                
                if l['status_id'] in (87609514, 87609510) and l['created_at'] < thirty_days_ago:
                    is_junk = True
                    reason = "1 oydan beri harakatsiz"
                
                if is_junk:
                    junk_leads.append({
                        'id': l['id'],
                        'name': l.get('name', 'Nomsiz'),
                        'reason': reason
                    })
            page += 1
        else:
            break
            
    print(f"Total JUNK leads identified: {len(junk_leads)}")
    
    if junk_leads:
        with open("junk_leads_report.md", "w", encoding="utf-8") as f:
            f.write("# Keraksiz (Junk) Leadlar Ro'yxati\n\n")
            f.write("AmoCRM dagi javobsiz chatlar sababli bloklangan va API orqali tahrirlash imkonsiz bo'lgan barcha eskirgan so'rovlar ro'yxati.\n\n")
            f.write("| ID | Lead Nomi | Sabab | Havola |\n")
            f.write("|---|---|---|---|\n")
            for lead in junk_leads:
                link = f"https://jonbrandingagency.amocrm.ru/leads/detail/{lead['id']}"
                f.write(f"| {lead['id']} | {lead['name']} | {lead['reason']} | [Ko'rish]({link}) |\n")
        print("Report saved to junk_leads_report.md")

if __name__ == "__main__":
    main()
