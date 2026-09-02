import os
import sys
import re
import time
import requests
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CYRILLIC_TO_LATIN = {
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo', 'Ж': 'J',
    'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O',
    'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'X', 'Ц': 'Ts',
    'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sh', 'Ъ': '', 'Ы': 'I', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'j',
    'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
    'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'x', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'sh', 'ъ': '', 'ы': 'i', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'ў': 'o\'', 'Ў': 'O\'', 'қ': 'q', 'Қ': 'Q', 'ғ': 'g\'', 'Ғ': 'G\'', 'ҳ': 'h', 'Ҳ': 'H'
}

def transliterate(text: str) -> str:
    if not text:
        return text
    result = []
    for char in text:
        result.append(CYRILLIC_TO_LATIN.get(char, char))
    return "".join(result)

def format_phone(phone: str) -> str:
    if not phone:
        return ""
    # Remove everything except digits and plus
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    # If there are no digits after cleaning, return original
    digits_only = re.sub(r'\D', '', cleaned)
    if not digits_only:
        return phone
        
    if len(digits_only) == 9:
        return f"+998{digits_only}"
    elif len(digits_only) == 12 and digits_only.startswith("998"):
        return f"+{digits_only}"
    
    # If it's already +998... just return
    if cleaned.startswith("+998"):
        return cleaned
        
    # If the user has random formats but starts with 998...
    if digits_only.startswith("998"):
         return f"+{digits_only}"
         
    return cleaned

def fetch_recent_contacts(amo: AmoCRMSync, limit=1500):
    # Fetch contacts sorted by created_at desc
    contacts = []
    page = 1
    
    while len(contacts) < limit:
        url = f"{amo.base_url}/api/v4/contacts?order[created_at]=desc&limit=250&page={page}"
        resp = requests.get(url, headers=amo._get_headers(), timeout=30)
        
        if resp.status_code == 204: # No content
            break
            
        if resp.status_code == 200:
            data = resp.json()
            batch = data.get("_embedded", {}).get("contacts", [])
            if not batch:
                break
                
            contacts.extend(batch)
            page += 1
            time.sleep(0.5)
        else:
            logger.error(f"Error fetching contacts: {resp.status_code} {resp.text}")
            break
            
    return contacts[:limit]

def main():
    logger.info("Starting AmoCRM contact updater script (Cyrillic -> Latin, Phone -> +998)...")
    amo = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET,
        redirect_url=getattr(settings, "AMOCRM_REDIRECT_URI", "")
    )
    amo._load_token()
    
    if not amo.access_token:
        logger.error("AmoCRM token not found.")
        return
        
    logger.info("Fetching recent contacts...")
    # Since we imported 1241 contacts, fetch the last 1500
    recent_contacts = fetch_recent_contacts(amo, limit=1500)
    logger.info(f"Fetched {len(recent_contacts)} recent contacts.")
    
    # We will only update contacts created in the last 24 hours to be safe
    yesterday = time.time() - 86400
    
    updates = []
    for c in recent_contacts:
        created_at = c.get("created_at", 0)
        if created_at < yesterday:
            continue
            
        orig_name = c.get("name", "")
        new_name = transliterate(orig_name)
        
        cfs = c.get("custom_fields_values") or []
        phone_updated = False
        new_cfs = []
        
        for cf in cfs:
            if cf.get("field_code") == "PHONE":
                new_vals = []
                for val in cf.get("values", []):
                    orig_phone = val.get("value", "")
                    new_phone = format_phone(orig_phone)
                    
                    if orig_phone != new_phone:
                        phone_updated = True
                    
                    new_vals.append({
                        "value": new_phone,
                        "enum_code": val.get("enum_code", "MOB")
                    })
                
                new_cfs.append({
                    "field_id": cf.get("field_id"),
                    "field_code": "PHONE",
                    "values": new_vals
                })
            else:
                new_cfs.append(cf)
                
        if orig_name != new_name or phone_updated:
            update_payload = {
                "id": c.get("id"),
                "name": new_name
            }
            if phone_updated:
                update_payload["custom_fields_values"] = new_cfs
                
            updates.append(update_payload)
            
    logger.info(f"Found {len(updates)} contacts that need updating.")
    
    if not updates:
        return
        
    # Batch update (amoCRM allows max 250 per PATCH request)
    BATCH_SIZE = 250
    total_updated = 0
    url = f"{amo.base_url}/api/v4/contacts"
    
    for i in range(0, len(updates), BATCH_SIZE):
        batch = updates[i:i+BATCH_SIZE]
        try:
            resp = requests.patch(url, headers=amo._get_headers(), json=batch, timeout=30)
            if resp.status_code in [200, 201]:
                total_updated += len(batch)
                logger.info(f"Successfully updated batch. Total so far: {total_updated}")
            else:
                logger.error(f"Failed to update batch: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Error during patch: {e}")
            
        time.sleep(1)
        
    logger.info(f"Update complete! Total updated: {total_updated}")

if __name__ == "__main__":
    main()
