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
    
    # get_recent_contact_call_notes
    notes = await amocrm.get_recent_contact_call_notes(limit=5)
    print(json.dumps(notes, indent=2))

asyncio.run(run())
