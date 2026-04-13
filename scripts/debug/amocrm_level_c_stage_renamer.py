import asyncio
import logging
import sys
import requests

project_dir = r"c:\Users\baxti\.gemini\antigravity\playground\oisha-os"
sys.path.append(project_dir)

import settings
import amocrm_sync

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("stage_renamer")

async def rename_stages():
    amocrm = amocrm_sync.AmoCRMSync(
        subdomain=settings.settings.AMOCRM_SUBDOMAIN,
        client_id=settings.settings.AMOCRM_CLIENT_ID,
        client_secret=settings.settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.settings.AMOCRM_REDIRECT_URL
    )
    
    amocrm._load_token()
    headers = amocrm._get_headers()
    
    # Hunter = 10117998, Closer = 10123314
    
    # 1. Update Hunter stages
    # Sobiq: Malakalash kutilmoqda (80178218) -> Yangi so'rov
    # Sobiq: Bog'lanib bo'lmadi (80178234) -> Bog'lanib bo'lmadi (Keep)
    # Sobiq: Muloqot boshlandi (80178222) -> Muloqot boshlandi
    # Sobiq: Konsultatsiya / Uchrashuv (80178230) -> Uchrashuv belgilandi
    
    logger.info("Updating Hunter Pipeline (10117998)...")
    url_hunter = f"{amocrm.base_url}/api/v4/leads/pipelines/10117998/statuses"
    
    hunter_payload = [
        {"id": 80178218, "name": "Yangi so'rov (Aloqaga chiqing)", "color": "#fffd7f"},
        {"id": 80178234, "name": "Bog'lanib bo'lmadi", "color": "#f99ea3"},
        {"id": 80178222, "name": "Muloqot boshlandi", "color": "#ffe5a0"},
        {"id": 80178230, "name": "Uchrashuv belgilandi", "color": "#e0ffbb"}
    ]
    
    res = requests.patch(url_hunter, json=hunter_payload, headers=headers)
    logger.info(f"Hunter rename response: {res.status_code}")
    
    # 2. Update Closer stages
    # Sobiq: Tijorat taklifi yuborildi (80215322) -> Prezentatsiya & KP yuborildi
    # Sobiq: Kelishildi (80215326) -> Muzokara / Shartnoma
    # Sobiq: Dastlabki to'lov (80215330) -> 50% Avans olindi
    
    logger.info("Updating Closer Pipeline (10123314)...")
    url_closer = f"{amocrm.base_url}/api/v4/leads/pipelines/10123314/statuses"
    
    closer_payload = [
        {"id": 80215322, "name": "Prezentatsiya & KP yuborildi", "color": "#ffca86"},
        {"id": 80215326, "name": "Muzokara / Shartnoma", "color": "#fbc8d3"},
        {"id": 80215330, "name": "50% Avans olindi", "color": "#a1eec1"}
    ]
    res2 = requests.patch(url_closer, json=closer_payload, headers=headers)
    logger.info(f"Closer rename response: {res2.status_code}")
    
    
    # 3. Create Custom Field: "Uchrashuv formati"
    logger.info("Creating Custom Field 'Uchrashuv formati'...")
    url_fields = f"{amocrm.base_url}/api/v4/leads/custom_fields"
    
    field_payload = [
        {
            "name": "Uchrashuv formati",
            "type": "select",
            "enums": [
                {"value": "Online", "sort": 10},
                {"value": "Offline - Bizning ofis", "sort": 20},
                {"value": "Offline - Mijoz ofisi", "sort": 30},
                {"value": "Offline - Neytral hudud/Cafe", "sort": 40}
            ]
        }
    ]
    
    res3 = requests.post(url_fields, json=field_payload, headers=headers)
    logger.info(f"Custom Field creation response: {res3.status_code}")
    if res3.status_code in [200, 201]:
        logger.info(res3.json())
        
if __name__ == "__main__":
    asyncio.run(rename_stages())
