import asyncio
import json
import os
import sys

sys.path.insert(0, '/home/ubuntu/oisha-os')
os.chdir('/home/ubuntu/oisha-os')

from src.settings import settings
from src.api_server import _get_amocrm_instance

async def run():
    amocrm = _get_amocrm_instance()
    
    # Fetch notes for lead 47522354
    lead_id = 47522354
    notes = await amocrm.get_lead_notes(lead_id)
    filtered = [n for n in notes if "[AI_CALL_ANALYSIS]" not in str(n.get("params", {}).get("text", "")) and "[Oisha" not in str(n.get("params", {}).get("text", ""))]
    print(json.dumps(filtered, indent=2))

asyncio.run(run())
