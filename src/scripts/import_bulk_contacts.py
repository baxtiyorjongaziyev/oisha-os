import os
import sys
import csv
import time
import requests
import logging
import re

# Setup Python path to import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CSV_PATH = r"C:\Users\baxti\.gemini\antigravity\brain\b0cc85b0-aa9b-4ad4-980b-d7cfbd9c22ca\.system_generated\steps\4\content.md"

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
    cleaned = re.sub(r'[^\d+]', '', phone)
    digits_only = re.sub(r'\D', '', cleaned)
    if not digits_only:
        return phone
    if len(digits_only) == 9:
        return f"+998{digits_only}"
    elif len(digits_only) == 12 and digits_only.startswith("998"):
        return f"+{digits_only}"
    if cleaned.startswith("+998"):
        return cleaned
    if digits_only.startswith("998"):
         return f"+{digits_only}"
    return cleaned

def parse_csv():
    contacts = []
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        # Skip the Markdown metadata header
        header_line = ""
        for line in f:
            if line.startswith(" ,Ism / Kontakt") or line.startswith("ID,Ism"):
                header_line = line
                break
        
        # Read the rest of the lines
        csv_reader = csv.reader([header_line] + f.readlines())
        headers = next(csv_reader)
        
        for row in csv_reader:
            if not row or len(row) < 3:
                continue
            
            # Map columns
            # headers: [0:ID, 1:Ism, 2:Tel1, 3:Tel2, 4:Telegram, 5:Kompaniya, 6:Guruh, 7:Kanal, 8:Sotuvchi, 9:Bosqich, 10:Sifat, ...]
            try:
                contact_id_str = row[0]
                name = transliterate(row[1].strip())
                tel1 = format_phone(row[2].strip())
                tel2 = format_phone(row[3].strip() if len(row) > 3 else "")
                tg = row[4].strip() if len(row) > 4 else ""
                company = row[5].strip() if len(row) > 5 else ""
                source = row[6].strip() if len(row) > 6 else ""
                sotuvchi = row[8].strip() if len(row) > 8 else ""
                izoh = row[18].strip() if len(row) > 18 else ""
                
                if not name and not tel1 and not tg:
                    continue
                if not name:
                    name = "Noma'lum kontakt"
                
                contacts.append({
                    "name": name,
                    "tel1": tel1,
                    "tel2": tel2,
                    "tg": tg,
                    "company": company,
                    "source": source,
                    "sotuvchi": sotuvchi,
                    "izoh": izoh
                })
            except Exception as e:
                logger.error(f"Row parsing error: {e}")
                
    return contacts

def create_bulk_contacts(amo: AmoCRMSync, batch: list):
    url = f"{amo.base_url}/api/v4/contacts"
    
    payload = []
    for c in batch:
        contact_data = {
            "name": c["name"],
            "custom_fields_values": []
        }
        
        # Add Phones
        phone_values = []
        if c["tel1"]:
            phone_values.append({"value": c["tel1"], "enum_code": "MOB"})
        if c["tel2"]:
            phone_values.append({"value": c["tel2"], "enum_code": "MOB"})
            
        if phone_values:
            contact_data["custom_fields_values"].append({
                "field_code": "PHONE",
                "values": phone_values
            })
            
        payload.append(contact_data)
        
    try:
        response = requests.post(url, headers=amo._get_headers(), json=payload, timeout=30)
        if response.status_code in [200, 201]:
            result = response.json()
            created_contacts = result.get("_embedded", {}).get("contacts", [])
            return created_contacts
        else:
            logger.error(f"Bulk create failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Bulk API error: {e}")
        return None

def add_notes_to_contacts(amo: AmoCRMSync, contacts_with_ids: list, original_batch: list):
    url = f"{amo.base_url}/api/v4/contacts/notes"
    
    payload = []
    for idx, c_resp in enumerate(contacts_with_ids):
        c_id = c_resp.get("id")
        orig = original_batch[idx]
        
        # Build note text
        note_lines = []
        if orig["company"]: note_lines.append(f"🏢 Kompaniya: {orig['company']}")
        if orig["tg"]: note_lines.append(f"✈️ Telegram: {orig['tg']}")
        if orig["source"]: note_lines.append(f"🔗 Manba: {orig['source']}")
        if orig["sotuvchi"]: note_lines.append(f"👤 Mas'ul sotuvchi: {orig['sotuvchi']}")
        if orig["izoh"]: note_lines.append(f"📝 Izoh: {orig['izoh']}")
        
        note_text = "\n".join(note_lines)
        
        if note_text:
            payload.append({
                "entity_id": c_id,
                "note_type": "common",
                "params": {
                    "text": note_text
                }
            })
            
    if payload:
        try:
            response = requests.post(url, headers=amo._get_headers(), json=payload, timeout=30)
            if response.status_code not in [200, 201]:
                logger.error(f"Notes create failed: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Notes API error: {e}")

def main():
    logger.info("Starting AmoCRM bulk import script...")
    
    # Initialize amoCRM client
    amo = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET,
        redirect_url=getattr(settings, "AMOCRM_REDIRECT_URI", "")
    )
    amo._load_token()
    
    if not amo.access_token:
        logger.error("AmoCRM token not found or invalid.")
        return
        
    contacts = parse_csv()
    logger.info(f"Parsed {len(contacts)} contacts from CSV.")
    
    # Process in batches of 50
    BATCH_SIZE = 50
    total_imported = 0
    
    for i in range(0, len(contacts), BATCH_SIZE):
        batch = contacts[i:i+BATCH_SIZE]
        logger.info(f"Processing batch {i//BATCH_SIZE + 1} ({len(batch)} contacts)...")
        
        # Create contacts
        created_contacts = create_bulk_contacts(amo, batch)
        if created_contacts:
            # Add notes
            add_notes_to_contacts(amo, created_contacts, batch)
            total_imported += len(created_contacts)
            logger.info(f"Successfully imported {len(created_contacts)} contacts. Total so far: {total_imported}")
        
        # Sleep to avoid rate limits (amoCRM allows 7 req/sec usually, but let's be safe)
        time.sleep(1.5)
        
    logger.info(f"Import completed! Total contacts imported: {total_imported}")

if __name__ == "__main__":
    main()
