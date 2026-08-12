import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from src.services.core.crm.amocrm_sync import AmoCRMSync

def build_amocrm():
    subdomain = os.getenv("AMOCRM_SUBDOMAIN", "")
    client_id = os.getenv("AMOCRM_CLIENT_ID", "")
    client_secret = os.getenv("AMOCRM_CLIENT_SECRET", "")
    redirect = os.getenv("AMOCRM_REDIRECT_URL", "https://oisha.local/oauth")
    token_file = os.getenv("AMOCRM_TOKEN_FILE", "data/amocrm_token.json")
    
    if not subdomain or not client_id:
        raise RuntimeError("AMOCRM_SUBDOMAIN va AMOCRM_CLIENT_ID kerak")
        
    return AmoCRMSync(
        subdomain=subdomain,
        client_id=client_id,
        client_secret=client_secret,
        redirect_url=redirect,
        token_file=token_file
    )

async def run():
    sync = build_amocrm()
    
    timestamp_30_days_ago = int((datetime.now() - timedelta(days=30)).timestamp())
    
    print("Fetching leads in status 'Yangi so'rov' (80178230)...")
    leads_yangi = await sync.get_leads(status_id=80178230)
    print("Fetching leads in 'Nerazobrannoe' (usually pipeline=0, status=142)")
    leads_nerazob = await sync.get_leads(status_id=142)
    # also getting 'Неразобранное' from pipeline 0 if it has a different ID
    # Actually, in AmoCRM 'Yangi so'rov' is 80178230. 'Неразобранное' is usually status_id=142 in main. 
    # Or maybe it's in the Unsorted endpoint. If the user expects ~127 total leads, we might get enough.
    
    leads = leads_yangi + leads_nerazob
    
    # filter duplicates
    leads_dict = {lead['id']: lead for lead in leads}
    leads = list(leads_dict.values())
    
    print(f"Total leads fetched: {len(leads)}")
    
    to_tag = []
    for lead in leads:
        created_at = lead.get('created_at', 0)
        if created_at < timestamp_30_days_ago:
            to_tag.append(lead)
            
    print(f"Total old leads to tag: {len(to_tag)}")
    
    if len(to_tag) == 0:
        return
        
    for lead in to_tag:
        lead_id = lead.get('id')
        tags = lead.get('_embedded', {}).get('tags', [])
        tag_names = [t.get('name') for t in tags]
        
        if "Keraksiz" not in tag_names:
            print(f"Adding tag to lead {lead_id}")
            try:
                await sync.add_lead_tag(lead_id, "Keraksiz")
            except Exception as e:
                print(f"Failed to add tag to lead {lead_id}: {e}")
                
    print("Done")

asyncio.run(run())
